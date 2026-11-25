from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import pydicom
import streamlit as st

from PIL import Image as PILImage
from pydicom.errors import InvalidDicomError

from modules.common import (
    VIDEO_CONTRAST,
    VIDEO_FPS,
    VIDEO_WIDTH,
    FileHandler,
    convert_image_to_video,
    retrieve_images_from_zip,
)


@dataclass
class DicomImage:
    name: str
    data: bytes


@dataclass
class Series:
    images: list[DicomImage] = field(default_factory=list)
    video: Optional[bytes] = None


class DicomHandler(FileHandler):

    @classmethod
    def load(cls, upload) -> None:
        series = Series()

        for file in upload:
            suffix = Path(file.name).suffix.lower()

            if suffix == ".zip":
                retrieved_from_zip = retrieve_images_from_zip(file.getvalue(), "dicom")
                files = [DicomImage(file.name, file.data) for file in retrieved_from_zip]
                if files:
                    series.images += files
            elif suffix in [".dcm", ".dicom", ""]:
                try:
                    pydicom.dcmread(
                        BytesIO(file.getvalue()),
                        stop_before_pixels=True,
                    )

                    series.images.append(
                        DicomImage(
                            name=file.name,
                            data=file.getvalue(),
                        )
                    )

                except InvalidDicomError, OSError:
                    continue

        if not series.images:
            raise ValueError("No DICOM files found in the upload.")

        st.session_state["dicom"] = series

        st.session_state["dicom"].video = convert_image_to_video(
            images=cls.__dicom_files_to_images(
                [image.data for image in series.images]),
                fps=VIDEO_FPS,
                contrast=VIDEO_CONTRAST,
        )

        pass

    @classmethod
    def show(cls) -> None:
        st.markdown("##### :material/database: Image Data", anchors=False)
        with st.expander("Files", width=300 + 60):
            [st.write(image.name) for image in st.session_state["dicom"].images]
        st.markdown("##### :material/settings: Settings", anchors=False)
        with st.expander(
                        "Video",
                        width=300 + 60,
                    ):
            st.selectbox("Video Width", [200, VIDEO_WIDTH, 600, 800], index=1, key="dicom_video_width")
            st.slider("Contrast", min_value=0.1, max_value=2.0, value=VIDEO_CONTRAST, step=0.1, key="dicom_video_contrast", on_change=cls.__rerender_images_to_video)
            st.button("Reset to Default", on_click=cls.__reset_video_settings)

        st.video(st.session_state["dicom"].video, width=st.session_state["dicom_video_width"], format="video/mp4", start_time=0)


    @classmethod
    def __reset_video_settings(cls) -> None:
        st.session_state["dicom_video_width"] = VIDEO_WIDTH
        st.session_state["dicom_video_contrast"] = VIDEO_CONTRAST
        cls.__rerender_images_to_video()


    @classmethod
    def __rerender_images_to_video(cls):
        st.session_state["dicom"].video = convert_image_to_video(
                cls.__dicom_files_to_images(
                [image.data for image in st.session_state["dicom"].images]),
                fps=VIDEO_FPS,
                contrast=st.session_state["dicom_video_contrast"]
        )

    @classmethod
    def __dicom_files_to_images(
        cls,
        dicom_files: list[bytes],
    ) -> list[bytes]:

        images: list[bytes] = []

        for dicom_bytes in dicom_files:
            ds = pydicom.dcmread(BytesIO(dicom_bytes))

            pixels = ds.pixel_array.astype(np.float32)

            pixels -= pixels.min()

            if pixels.max() > 0:
                pixels /= pixels.max()

            pixels = (pixels * 255).astype(np.uint8)

            image = PILImage.fromarray(pixels).convert("RGB")

            buffer = BytesIO()
            image.save(buffer, format="PNG")

            images.append(buffer.getvalue())

        return images
