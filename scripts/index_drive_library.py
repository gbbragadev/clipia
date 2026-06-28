"""Indexa as pastas do Drive (rclone) nas tags de template. Roda sob demanda no venv312:

    .\\.venv312\\Scripts\\python scripts\\index_drive_library.py

Nao baixa videos — so cataloga os caminhos remotos (listagem recursiva via rclone).
O download e sob demanda (pick_clip -> pick_drive_clip -> cache).

Se o binario rclone (winget) nao estiver no PATH do processo, aponte via env:
    $env:RCLONE_EXE = "C:\\...\\rclone.exe"
    .\\.venv312\\Scripts\\python scripts\\index_drive_library.py
"""

from app.services.drive_library import FOLDER_TAG_MAP, count_for_tag, index_all


def main() -> None:
    n_folders = sum(len(v) for v in FOLDER_TAG_MAP.values())
    print(f"Indexando {n_folders} pastas em {len(FOLDER_TAG_MAP)} tags (rclone recursivo)...")
    totals = index_all()
    print("\n=== Resumo por tag ===")
    for tag in FOLDER_TAG_MAP:
        print(f"  {tag:<14} {count_for_tag(tag):>6} clips")
    total = sum(totals.values())
    print(f"\nTotal indexado: {total} clips em {len(FOLDER_TAG_MAP)} tags.")


if __name__ == "__main__":
    main()
