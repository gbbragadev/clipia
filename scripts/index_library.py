"""Indexa embeddings CLIP dos clips da biblioteca do Drive. Batch one-time na GPU (GTX 1660).

Uso (no venv312, com RCLONE_EXE apontado):
    .\\.venv312\\Scripts\\python scripts\\index_library.py              # todas as tags
    .\\.venv312\\Scripts\\python scripts\\index_library.py satisfying   # so uma tag
    .\\.venv312\\Scripts\\python scripts\\index_library.py satisfying 200  # amostra (limit)

Idempotente: pula clips ja embeddados (WHERE embedding IS NULL). Baixa em batch por pasta
(--files-from; 1 listagem por pasta) e embedda 1 frame-chave de cada clip com CLIP ViT-B/32.
"""

import sys

from app.services.drive_library import FOLDER_TAG_MAP, count_for_tag, index_embeddings


def main() -> None:
    args = sys.argv[1:]
    if args:
        tags = [args[0]]
        limit = int(args[1]) if len(args) > 1 else None
    else:
        tags = list(FOLDER_TAG_MAP)
        limit = None
    for tag in tags:
        n = index_embeddings(tag, limit=limit)
        print(f"[{tag}] {n} embeddados (total da tag: {count_for_tag(tag)})")


if __name__ == "__main__":
    main()
