"""Build a reproducible standalone prompt kit, not a furniture manufacturing pack.

Usage: python /path/to/playbooks/furniture/package.py [--output /target/folder]
Only the Python standard library is required. Historical differing releases
are never overwritten; change the version before changing a published kit.
"""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import argparse
import hashlib
import io
import json


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    source = Path(__file__).resolve().parent
    repo = source.parents[1]
    release = json.loads((source / 'release.json').read_text())
    version = release['version']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=repo / f'outputs/furniture-prompt-v{version}')
    args = parser.parse_args()
    prompt = (source / 'prompt.md').read_bytes()
    frozen = repo / release['tested_prompt_source']
    assert sha(frozen.read_bytes()) == release['tested_prompt_sha256']
    assert prompt.decode().split('\n', 1)[1] == frozen.read_text().split('\n', 1)[1]
    assert sha(prompt) == release['release_prompt_sha256']
    items = {name: (source / name).read_bytes()
             for name in ('prompt.md', 'brief.md', 'checks.md', 'release.json')}
    items['START.md'] = (
        f'# Мебельный проект · промпт v{version}\n\n'
        'Скопируйте весь текст [prompt.md](prompt.md) в новый чат и добавьте '
        'описание задачи под вводными пользователя. Шаблон [brief.md](brief.md) '
        'можно заполнить частично. [checks.md](checks.md) помогает оценить '
        'готовность результата.\n\n'
        'Проверены первые ответы на две текстовые задачи в новых чатах. '
        'Полный цикл CAD, поиска поставщиков, выпуска чертежей и физическая '
        'сборка этой пробой не проверены. Данные о выпуске — '
        '[release.json](release.json). Сам промпт не добавляет модели инструменты.\n'
    ).encode()
    args.output.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    year, month, day = map(int, release['date'].split('-'))
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(items.items()):
            info = ZipInfo(name, (year, month, day, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    payload = buffer.getvalue()
    path = args.output / f'furniture-prompt-v{version}.zip'
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError('A different kit already exists: preserve it and bump the version')
    path.write_bytes(payload)
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(items)
        for name, data in items.items():
            assert archive.read(name) == data
    manifest = dict(version=version,archive=path.name,archive_sha256=sha(payload),
                    files={name: sha(data) for name, data in sorted(items.items())},
                    scope=release['scope'])
    (args.output / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Prompt kit v{version}: {len(items)} files, {len(payload)} bytes; verified')


if __name__ == '__main__':
    main()
