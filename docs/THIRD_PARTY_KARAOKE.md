# Karaoke AI · third-party attribution

**English / Русский**

## UVR model / Модель UVR

Emberbox optionally downloads **UVR_MDXNET_9482.onnx**, trained/distributed by
the **Ultimate Vocal Remover** project and its contributors, including
**Anjok07 and aufr33**. Credit also goes to **KUIELab / Woosung Choi** for the
MDX-Net architecture. Emberbox does not claim authorship of these weights.

Emberbox загружает необязательную модель **UVR_MDXNET_9482.onnx** проекта
**Ultimate Vocal Remover**. Благодарим авторов и участников, включая
**Anjok07 и aufr33**, а также **KUIELab / Woosung Choi** за архитектуру MDX-Net.
Авторство весов не принадлежит Emberbox.

- [UVR project and its model licensing statement](https://github.com/Anjok07/ultimatevocalremovergui#license)
- [Authors' public model release](https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models)
- [Original model asset](https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR_MDXNET_9482.onnx)
- [UVR's framing and compensation metadata](https://github.com/Anjok07/ultimatevocalremovergui/blob/master/models/MDX_Net_Models/model_data/model_data.json)
- [KUIELab MDX-Net](https://github.com/kuielab/mdx-net)

The upstream UVR README explicitly asks third-party developers using its models
to honour the MIT licence and credit UVR and its developers. This attribution
applies to the specific UVR model above; it does not declare a licence for every
third-party model distributed by UVR. Weights are downloaded directly from the
authors by the optional setup tool; they are not included in this repository.
Installed inference packages retain their own licence notices in the private
runtime.

README UVR прямо просит сторонних разработчиков, использующих модели, соблюдать MIT и
указывать UVR и авторов. Эти сведения относятся к конкретной модели выше;
лицензия всех сторонних моделей каталога UVR не подразумевается. Веса скачиваются
непосредственно у авторов и не входят в репозиторий Emberbox. Зависимости
сохраняют свои лицензионные уведомления в отдельной установленной среде.

## Integrity / Целостность

```text
File:   UVR_MDXNET_9482.onnx
Bytes:  29704436
SHA256: f4f365207c56deb115bceedff3ad8fe98a751c745f9e370cecec6226b8b47184
UVR metadata key (MD5 of final 10000 KiB): 0ddfc0eb5792638ad5dc27850236c246
```

The original SHA256 is verified before inference. The model's learned tensors
are unchanged. Only its input/output time-dimension declarations are shortened
from 256 to 64 frames in memory for bounded CPU streaming. Host STFT uses
FFT6144, hop1024, dim_f2048 at 44.1 kHz and UVR's vocal compensation1.035.

До обработки проверяется SHA256 исходного файла. Обученные тензоры не меняются.
В памяти сокращается только объявление временного размера входа/выхода с 256 до
64 кадров для потоковой CPU-обработки. STFT: FFT6144, шаг1024, dim_f2048,
44,1 кГц; коэффициент вокала UVR1.035.

## Quality checks / Проверки качества

The implementation is tested with original generated PCM and an original
eSpeak-NG spoken fixture mixed with synthetic centred accompaniment. The latter
checks preservation against known accompaniment; it is not a music-catalogue
benchmark or a guarantee for a particular song. Real models can leave artifacts.
No user account data or song recordings are included in tests or preview images.

Проверки используют собственные сигналы и оригинальную фразу eSpeak-NG с
синтезированным сопровождением в центре. Известная дорожка сопровождения позволяет
сравнить сохранение инструментов. Это не тест всего музыкального каталога и не
гарантия качества отдельной песни; возможны артефакты. Данные аккаунтов и записи
песен пользователя не входят в тесты и превью.
