import os
import sys
import json
from pathlib import Path, PurePath
import tempfile
import shutil
import zipfile

from androguard.core.bytecodes.apk import APK

class XAPK:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.apk_src = None
        self.obb_files = []
        self.apk = None
        self.manifest = None
        self.icon = None
        self.initialize()

    def initialize(self):
        for x in self.folder.glob('*.apk'):
            self.apk_src = Path(x)
        for x in self.folder.glob('*.obb'):
            self.obb_files.append(Path(x))
        
        self.apk = APK(self.apk_src)
        self.manifest = self.make_manifest()
        self.icon = self.apk.get_file(self.apk.get_app_icon())

    def make_manifest(self):
        apk_size = self.apk_src.stat().st_size
        total_size = apk_size
        
        obb_info = []
        for obb_file in self.obb_files:
            obb_size = obb_file.stat().st_size
            total_size += obb_size

            obb_info.append({
                'file': f'Android/obb/{self.apk.get_package()}/{obb_file.name}',
                'install_location': 'EXTERNAL_STORAGE',
                'install_path': f'Android/obb/{self.apk.get_package()}/{obb_file.name}'
            })

        manifest = {
            'xapk_version': 1,
            'package_name': self.apk.get_package(),
            'name': self.apk.get_app_name(),
            'version_code': self.apk.get_androidversion_code(),
            'version_name': self.apk.get_androidversion_name(),
            'min_sdk_version': self.apk.get_min_sdk_version(),
            'target_sdk_version': self.apk.get_target_sdk_version(),
            'permissions': self.apk.get_permissions(),
            'total_size': total_size,
            'expansions': obb_info,
        }

        return manifest

    def save(self):
        self.name = f'{self.apk.get_package()}_v{self.apk.get_androidversion_name()}.xapk'
        zip_path = self.folder.joinpath(self.name)

        zip_dir = tempfile.mkdtemp()
        try:
            print('copying apk to temp directory...')
            apk_name = f'{self.apk.get_package()}.apk'
            apk_src = self.apk_src.resolve()
            apk_dest = PurePath(zip_dir).joinpath(apk_name)
            shutil.copy2(apk_src, apk_dest)
            print('apk: OK')

            for obb_file in self.obb_files:
                print(f'copying {obb_file.name} to temp directory...')
                obb_name = f'Android/obb/{self.apk.get_package()}/{obb_file.name}'
                obb_src = obb_file.resolve()
                obb_dest = PurePath(zip_dir).joinpath(obb_name)
                os.makedirs(Path(obb_dest).parent, exist_ok=True)
                shutil.copy2(obb_src, obb_dest)
                print(f'{obb_file.name}: OK')

            print('creating icon in temp directory...')
            icon = self.icon
            icon_dest = PurePath(zip_dir).joinpath('icon.png')
            with open(icon_dest, 'wb') as iconfile:
                iconfile.write(icon)
            print('icon: OK')

            print('creating manifest in temp directory...')
            manifest_dest = PurePath(zip_dir).joinpath('manifest.json')
            with open(manifest_dest, 'w') as manifestfile:
                json.dump(self.manifest, manifestfile, indent=4)
            print('manifest: OK')

            print('creating xapk archive...')
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zfd:
                for root, dirs, files in os.walk(zip_dir):
                    for f in files:
                        filename = os.path.join(root, f)
                        zfd.write(filename, os.path.relpath(filename, zip_dir))
            print('xapk: OK')
        finally:
            print('cleaning up temp directory...')
            shutil.rmtree(zip_dir)
            print('cleanup: OK')

def main(args):
    folder = args[0]
    xapk = XAPK(folder)
    xapk.save()

if __name__ == '__main__':
    main(sys.argv[1:])
