from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import Final
from zipfile import ZipFile
import av
import numpy as np
import pydicom
from pydicom.pixel_data_handlers.util import (
    apply_color_lut,
    apply_modality_lut,
    apply_voi_lut,
)
from PIL import Image, ImageEnhance

VIDEO_WIDTH: Final[int] = 400
VIDEO_FPS: Final[int] = 3
VIDEO_CONTRAST: Final[float] = 0.7


class FileHandler(ABC):

    @classmethod
    @abstractmethod
    def load(cls, upload) -> None:
        pass

    @classmethod
    @abstractmethod
    def show(cls) -> None:
        pass


def convert_dicom_to_mp4(
    files: list[pydicom.Dataset],
    fps: int = 10,
    contrast: float = 1.0,
    inverted: bool = False,
) -> bytes:
    if contrast <= 0:
        raise ValueError("Contrast must be greater than zero")

    frames = []

    for ds in files:
        try:
            frame = ds.pixel_array
            frame = apply_modality_lut(frame, ds)
            frame = apply_voi_lut(frame, ds)
        except Exception:
            import traceback

            traceback.print_exc()
            continue

        frame = frame.astype(np.float32)

        # robust normalization
        low, high = np.percentile(frame, [1, 99])

        frame = np.clip(frame, low, high)

        if high > low:
            frame = (frame - low) / (high - low)

        frame = np.clip((frame - 0.5) * contrast + 0.5, 0.0, 1.0)
        frame = (frame * 255).astype(np.uint8)

        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)
            frames.append(frame)

        elif frame.ndim == 3:
            if frame.shape[-1] == 3:
                frames.append(frame)
            else:
                for single_frame in frame:
                    rgb = np.stack([single_frame] * 3, axis=-1)
                    frames.append(rgb)

    if not frames:
        raise ValueError("No valid DICOM frames")

    h, w = frames[0].shape[:2]

    output = BytesIO()

    with av.open(output, "w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)

        stream.width = w
        stream.height = h
        stream.pix_fmt = "yuv420p"

        # much higher quality than FFmpeg defaults
        stream.options = {
            "crf": "10",
            "preset": "slow",
        }

        for frame in frames:
            video = av.VideoFrame.from_ndarray(frame, format="rgb24")

            for packet in stream.encode(video):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)

    return output.getvalue()


def convert_image_to_video(
    images: list[bytes],
    fps: int = 10,
    contrast: float = 1.0,
) -> bytes:
    if not images:
        raise ValueError("images must not be empty")

    width, height = Image.open(BytesIO(images[0])).size
    output = BytesIO()

    with av.open(output, "w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        for image_bytes in images:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")

            if contrast != 1.0:
                image = ImageEnhance.Contrast(image).enhance(contrast)

            frame = av.VideoFrame.from_image(image)

            for packet in stream.encode(frame):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)

    return output.getvalue()


def calc_age(birth_date):
    if not birth_date:
        return "N/A"
    from datetime import datetime

    try:
        birth_date = datetime.strptime(birth_date, "%Y%m%d")
    except ValueError:
        return "N/A"

    today = datetime.today()
    age = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )
    return age


from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pydicom
from pydicom.errors import InvalidDicomError


@dataclass
class File:
    name: str
    data: bytes


def retrieve_images_from_zip(
    zip_bytes: bytes,
    filetype: str,
) -> list[File]:
    """
    Retrieve all files of a given type from a ZIP archive.

    Supported filetypes:
    - png
    - jpg (matches .jpg and .jpeg)
    - jpeg (matches .jpg and .jpeg)
    - dicom (matches .dcm and extensionless DICOM files)
    """
    filetype = filetype.lower()

    extensions = {
        "png": {".png"},
        "jpg": {".jpg", ".jpeg"},
        "jpeg": {".jpg", ".jpeg"},
        "dicom": {".dcm"},
    }

    if filetype not in extensions:
        raise ValueError(
            f"Unsupported filetype '{filetype}'. " f"Supported: {', '.join(extensions)}"
        )

    result: list[File] = []

    with ZipFile(BytesIO(zip_bytes)) as zip_file:
        for name in zip_file.namelist():
            if name.endswith("/"):
                continue

            data = zip_file.read(name)
            lower_name = name.lower()

            if any(lower_name.endswith(ext) for ext in extensions[filetype]):
                result.append(
                    File(
                        name=name.rsplit("/", 1)[-1],
                        data=data,
                    )
                )
                continue

            if filetype == "dicom" and Path(name).suffix == "":
                try:
                    pydicom.dcmread(
                        BytesIO(data),
                        stop_before_pixels=True,
                    )

                    result.append(File(name=name.rsplit("/", 1)[-1], data=data))
                except InvalidDicomError, OSError:
                    pass

    return result