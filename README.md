# Cambusa · модульный шкаф

Высокий шкаф 1000 × 1800 × 500 мм с рамочными дверями, полками в створках и левым пегбордом и алюминиевым каркасом во всю высоту. Текущая версия v17.

**[Открыть 3D в браузере](https://padington.github.io/cambusa-cabinet/)** · [Ведомость и смета](outputs/cambusa-frame-v17/planning/BOM.md) · [Раскладка фанеры](outputs/cambusa-frame-v17/planning/cut-plan.svg) · [Статус проверок](outputs/cambusa-frame-v17/КОНСТРУКЦИЯ.md)

В просмотре можно вращать шкаф и выбирать закрытый вид, открытые двери и отдельный каркас. Локально откройте [docs/index.html](docs/index.html) в браузере. Для скачивания доступны [закрытая сборка](docs/closed.glb), [открытая сборка](docs/open.glb) и [рама](docs/frame.glb).

## Облегчённая версия

[3D v18 онлайн](https://padington.github.io/cambusa-cabinet/variants/v18/) · [Расчёт и сравнение](https://github.com/padington/cambusa-cabinet/blob/cambusa-v18/outputs/cambusa-frame-v18/ОБЛЕГЧЕНИЕ.md). Панели и полки 12 мм, восемь алюминиевых опор. v17 остаётся базовой моделью.

## Карта проекта

| Где | Что лежит |
|---|---|
| [work/](work/) | Исходники геометрии v17, функции построения и исходник 3D-просмотра |
| [scripts/](scripts/) | Команды пересборки модели, раскладки и сметы |
| [inputs/](inputs/) | Форматы заготовок, фурнитура и шаблон цен |
| [outputs/](outputs/) | Модели v15–v17, результаты расчётов, отчёты и карты раскроя |
| [docs/](docs/) | Просмотр для GitHub Pages и файлы для скачивания |
| [history/](history/README.md) | Снимки v01–v14, старые генераторы, входные данные и чертежи |
| [references/](references/README.md) | Источники по форме и фурнитуре, [фотогалерея](references/photos/README.md) |

## Версии и ветки

- [cambusa-v15](https://github.com/padington/cambusa-cabinet/tree/cambusa-v15) — деревянный корпус на отдельном основании и двери с полками.
- [cambusa-v16](https://github.com/padington/cambusa-cabinet/tree/cambusa-v16) — четыре цельные стойки от опор до крышки.
- [cambusa-v17](https://github.com/padington/cambusa-cabinet/tree/cambusa-v17) — пегборд слева, аудит 3D и эскизы хранения.
- [cambusa-v18](https://github.com/padington/cambusa-cabinet/tree/cambusa-v18) — отдельный вариант облегчения.
- `main` — текущая версия для просмотра. Для эксперимента создайте ветку от нужного тега. Выбор старой версии не требует сброса истории.

```sh
git switch -c experiment/rear-brace cambusa-v17
git switch --detach cambusa-v15
git switch main
```

## Пересборка

Python 3.11 или новее. Из корня репозитория:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build.py
```

Сборка проверяет геометрию и записывает GLB, карту раскроя и ведомость в `outputs/cambusa-frame-v17/`. Просмотр в `docs/` строится из той же геометрии. GitHub Pages публикует `main:/docs`.

## Раскладка и смета

1. Скрипт `scripts/plan.py` извлекает размеры деталей из закрытой сборки GLB. Он проверяет, что каждая деталь попала в раскладку ровно один раз и заготовки на листах не пересекаются.
2. В `inputs/stock.json` задаются форматы листов и хлыстов, технологические зазоры и позиции фурнитуры. Карты листов используют прямоугольные заготовки. Чистовые контуры и обработка хранятся в модели.
3. Скопируйте `inputs/prices.json` в `inputs/prices.local.json`, внесите цены поставщика за указанные единицы и запустите:

```sh
python scripts/plan.py --prices inputs/prices.local.json
```

Результаты с вашими ценами появятся в `local-estimate/`. Неоценённые позиции остаются отдельными строками. Стоимость неоценённых строк не включается в частичный итог. Цены, реальные артикулы соединителей и крепления к стене следует подтвердить перед заказом.

## Проверки и варианты наполнения

[Аудит 3D](outputs/cambusa-frame-v17/АУДИТ-3D.json) · [Схема открывания на 270°](outputs/cambusa-frame-v17/ход-270.svg) · [Коллажи хранения](outputs/cambusa-frame-v17/storage/README.md) · [Задачи GitHub](https://github.com/padington/cambusa-cabinet/issues)

## До заказа

v17 сверяет 53 детали в экспортированной модели и проверяет два крайних положения дверей. В работе остаются ход реальной петли, крепления деревянных вставок к каркасу, жёсткость и устойчивость. [Очередь работ](TODO.md).
