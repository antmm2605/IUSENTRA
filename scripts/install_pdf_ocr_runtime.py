"""Install pinned public OCR artifacts during image build, never at document read.

Only Linux x64 (the deployed/local Docker platform) is currently governed here.
Every download must match the immutable SHA-256 before extraction/installation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path
import platform
import tarfile
import urllib.request

ARTIFACTS = (
    ('pdfium', 'https://github.com/firecrawl/pdfium-rs/releases/download/native-v7988/firecrawl-pdfium-linux-x64.tgz', '6248189e07bbc33cdeb31976c539a88614307c8a19f3276dbd018efbe5b4a2a2'),
    ('onnx', 'https://github.com/microsoft/onnxruntime/releases/download/v1.27.0/onnxruntime-linux-x64-1.27.0.tgz', '547e40a48f1fe73e3f812d7c88a948612c23f896b91e4e2ee1e232d7b468246f'),
    ('models/pp-ocrv6_small_det.onnx', 'https://github.com/GreatV/oar-ocr/releases/download/v0.7.0/pp-ocrv6_small_det.onnx', 'd73e0058b7a8086bbd57f3d10b8bcd4ff95363f67e06e2762b5e814fe9c9410e'),
    ('models/pp-ocrv6_small_rec.onnx', 'https://github.com/GreatV/oar-ocr/releases/download/v0.7.0/pp-ocrv6_small_rec.onnx', '5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634'),
    ('models/ppocrv6_dict.txt', 'https://github.com/GreatV/oar-ocr/releases/download/v0.7.0/ppocrv6_dict.txt', 'b5f2bfe2bdd9448429e3e82b51c789775d9b42f2403d082b00662eb77e401c5d'),
)


def install(destination: Path) -> None:
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'AMD64'}:
        raise RuntimeError('Installazione OCR governata disponibile nel container Linux x64.')
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for relative, url, expected in ARTIFACTS:
        request = urllib.request.Request(url, headers={'User-Agent': 'IUSENTRA-OCR-build'})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(150_000_001)
        if len(data) > 150_000_000 or hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('Integrità del componente OCR non verificata: ' + relative)
        target = destination / relative
        if url.endswith('.tgz'):
            target.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                archive.extractall(target, filter='data')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        print('Verificato e installato: ' + relative, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    install(parser.parse_args().destination)
