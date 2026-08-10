import os
import shutil
from pathlib import Path


def sync_dir(src, dst):
    if not os.path.exists(src):
        return
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(dst):
        dst_item = os.path.join(dst, item)
        src_item = os.path.join(src, item)
        if not os.path.exists(src_item):
            if os.path.isdir(dst_item):
                shutil.rmtree(dst_item)
                print(f"Eliminado directorio obsoleto: {dst_item}")
            else:
                os.remove(dst_item)
                print(f"Eliminado archivo obsoleto: {dst_item}")
    for item in os.listdir(src):
        src_item = os.path.join(src, item)
        dst_item = os.path.join(dst, item)
        if os.path.isdir(src_item):
            if item == "__pycache__":
                continue
            sync_dir(src_item, dst_item)
        else:
            if (not os.path.exists(dst_item) or
                os.stat(src_item).st_mtime != os.stat(dst_item).st_mtime or
                os.stat(src_item).st_size != os.stat(dst_item).st_size):
                shutil.copy2(src_item, dst_item)
                print(f"Sincronizado: {src_item} -> {dst_item}")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    portable_dir = os.path.join(base_dir, "g360-stock-monitor-portable")

    if not os.path.exists(portable_dir):
        print(f"Error: No se encontro la carpeta portable '{portable_dir}'")
        return

    print("Iniciando sincronizacion con la version portable...")

    files_to_sync = [
        "main.py", "pyproject.toml", "requirements.txt",
        "run.bat", "launch.vbs", "launch_minimized.bat", "create_shortcut.vbs",
        "README.md", "build-portable.bat",
    ]
    for filename in files_to_sync:
        src_file = os.path.join(base_dir, filename)
        dst_file = os.path.join(portable_dir, filename)
        if os.path.exists(src_file):
            shutil.copy2(src_file, dst_file)
            print(f"Copiado: {filename} -> portable/{filename}")
        else:
            print(f"Omitido (no existe en origen): {filename}")

    sync_dir(os.path.join(base_dir, "src"), os.path.join(portable_dir, "src"))
    sync_dir(os.path.join(base_dir, "assets"), os.path.join(portable_dir, "assets"))

    for pyc in Path(portable_dir).rglob("__pycache__"):
        shutil.rmtree(pyc)

    print("\nSincronizacion finalizada con exito!")


if __name__ == "__main__":
    main()
