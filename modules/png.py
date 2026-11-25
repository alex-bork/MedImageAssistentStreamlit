from dataclasses import dataclass, field
from typing import Final, Optional
from pathlib import Path
from modules.common import VIDEO_CONTRAST, VIDEO_FPS, VIDEO_WIDTH, File, FileHandler, convert_image_to_video, retrieve_images_from_zip
import streamlit as st


class WrongFileTypeError(Exception):
    def __init__(self):
        super().__init__("Different file type than PNG not allowed.")


@dataclass
class PngImage:
    name: str
    data: bytes


@dataclass
class Series:
    images: list[bytes] = field(default_factory=list)
    video: Optional[bytes] = None


class PngHandler(FileHandler):

    @classmethod
    def load(cls, uploads) -> None:

        series = Series()

        for upload in uploads:
            if Path(upload.name).suffix.lower() in [".zip"]:
                retrieved_from_zip = retrieve_images_from_zip(upload.getvalue(), "png")
                files = [PngImage(file.name, file.data) for file in retrieved_from_zip]
                if files:
                    series.images += files
            elif Path(upload.name).suffix.lower() in [".png"]:
                series.images.append(PngImage(upload.name, upload.getvalue()))
            else:
                continue

        if not series.images:
            raise ValueError("No PNG files found in the upload.")

        st.session_state["png"] = series

        st.session_state["png"].video = convert_image_to_video(
                [image.data for image in st.session_state["png"].images],
                fps=VIDEO_FPS,
                contrast=VIDEO_CONTRAST
        )

    @classmethod
    def show(cls) -> None:
        st.markdown("##### :material/database: Image Data", anchors=False)
        with st.expander("Files", width=300 + 60):
            [st.write(image.name) for image in st.session_state["png"].images]
        st.markdown("##### :material/settings: Settings", anchors=False)
        with st.expander(
                        "Video",
                        width=300 + 60,
                    ):
            st.selectbox("Video Width", [200, VIDEO_WIDTH, 600, 800], index=1, key="png_video_width")
            st.slider("Contrast", min_value=0.1, max_value=2.0, value=VIDEO_CONTRAST, step=0.1, key="png_video_contrast", on_change=cls.__rerender_images_to_video)
            st.button("Reset to Default", on_click=cls.__reset_video_settings)
        st.video(st.session_state["png"].video, width=st.session_state["png_video_width"], format="video/mp4", start_time=0)


    @classmethod
    def __reset_video_settings(cls) -> None:
        st.session_state["png_video_width"] = VIDEO_WIDTH
        st.session_state["png_video_contrast"] = VIDEO_CONTRAST
        cls.__rerender_images_to_video()


    @classmethod
    def __rerender_images_to_video(cls):
        st.session_state["png"].video = convert_image_to_video(
                [image.data for image in st.session_state["png"].images],
                fps=VIDEO_FPS,
                contrast=st.session_state["png_video_contrast"]
        )
