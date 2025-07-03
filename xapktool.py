import os
import sys
import json
import shutil
import zipfile
import tempfile
from pathlib import Path, PurePath
from androguard.core.apk import APK

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
        try:
            if not self.folder.is_dir():
                raise ValueError(f"The specified folder '{self.folder}' does not exist or is not a directory.")
            
            for x in self.folder.glob('*.apk'):
                self.apk_src = Path(x)
            if not self.apk_src:
                raise FileNotFoundError("No APK file found in the specified folder.")
            for x in self.folder.glob('*.obb'):
                self.obb_files.append(Path(x))
            if not self.obb_files:
                raise FileNotFoundError("No OBB files found in the specified directory.")

            self.apk = APK(self.apk_src)
            self.manifest = self.make_manifest()
            self.icon = self.apk.get_file(self.apk.get_app_icon())

            print("Verifying APK and OBB...")            
            apk_package_name = self.apk.get_package()
            for i, obb_file in enumerate(self.obb_files):
                obb_package_name = ".".join([obb.stem.split(".")[2:] for obb in self.obb_files][i])
                if obb_package_name != apk_package_name:
                    raise ValueError("The APK and OBB files do not belong to the same app.")
            print("Verification: OK")
            
        except Exception as e:
            raise RuntimeError(f"Initialization: {e}")

    def make_manifest(self):
        try:
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
        except Exception as e:
            raise RuntimeError(f"Manifest creation: {e}")

    def save(self):
        try:
            if not self.apk_src:
                raise ValueError("APK file source is not initialized.")

            self.name = f'{self.apk.get_package()}_v{self.apk.get_androidversion_name()}.xapk'
            zip_path = self.folder.joinpath(self.name)

            zip_dir = tempfile.mkdtemp()
            try:
                print('Copying APK to temp directory...')
                apk_name = f'{self.apk.get_package()}.apk'
                apk_src = self.apk_src.resolve()
                apk_dest = PurePath(zip_dir).joinpath(apk_name)
                shutil.copy2(apk_src, apk_dest)
                print('APK: OK')

                for obb_file in self.obb_files:
                    print(f'Copying {obb_file.name} to temp directory...')
                    obb_name = f'Android/obb/{self.apk.get_package()}/{obb_file.name}'
                    obb_src = obb_file.resolve()
                    obb_dest = PurePath(zip_dir).joinpath(obb_name)
                    os.makedirs(Path(obb_dest).parent, exist_ok=True)
                    shutil.copy2(obb_src, obb_dest)
                    print(f'{obb_file.name}: OK')

                print('Creating icon in temp directory...')
                icon = self.icon
                icon_dest = PurePath(zip_dir).joinpath('icon.png')
                with open(icon_dest, 'wb') as iconfile:
                    iconfile.write(icon)
                print('Icon: OK')

                print('Creating manifest in temp directory...')
                manifest_dest = PurePath(zip_dir).joinpath('manifest.json')
                with open(manifest_dest, 'w') as manifestfile:
                    json.dump(self.manifest, manifestfile, indent=4)
                print('Manifest: OK')

                print('Creating XAPK archive...')
                with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zfd:
                    for root, dirs, files in os.walk(zip_dir):
                        for f in files:
                            filename = os.path.join(root, f)
                            zfd.write(filename, os.path.relpath(filename, zip_dir))
                print('XAPK: OK')
            finally:
                print('Cleaning up temp directory...')
                shutil.rmtree(zip_dir)
                print('Cleanup: OK')
        except Exception as e:
            raise RuntimeError(f"Saving: {e}")

def main(args):
    try:
        if len(args) != 1:
            print("Usage: python3 xapktool.py <apk_obb_directory>")
            return

        folder = args[0]
        xapk = XAPK(folder)
        xapk.save()
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")
    except RuntimeError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main(sys.argv[1:])
