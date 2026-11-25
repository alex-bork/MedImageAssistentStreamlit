import streamlit as st
from modules.common import FileHandler
from modules.dicom import DicomHandler
from modules.jpg import JpgHandler
from modules.png import PngHandler
from modules.texts import FILE_TYPE_HELP_TEXT
from modules.dicomdir import DicomdirHandler

st.set_page_config(page_title="Medical Image Assistent", page_icon="🩺", layout="wide")


class FileHandlerNotFound(Exception):
    def __init__(self):
        super().__init__("File handler class not found.")


def get_filehandler_class(filetype: str) -> FileHandler:

    if filetype == "DICOMDIR":
        return DicomdirHandler
    elif filetype == "DICOM":
        return DicomHandler
    elif filetype == "JPG":
        return JpgHandler
    elif filetype == "PNG":
        return PngHandler
    else:
        raise FileHandlerNotFound


def load_file(file):

    file_handler = get_filehandler_class(st.session_state["app_filetype"])
    st.session_state["filehandler"] = file_handler
    st.session_state["filehandler"].load(file)
    st.session_state["app_filetype_loaded"] = st.session_state["app_filetype"]


with st.sidebar:
    st.title("Medical Image Assistent", icon="🩺")

    st.space()

    st.selectbox(
        "Select the type of medical image file you want to upload:",
        ("DICOMDIR", "DICOM", "JPG", "PNG"),
        index=0,
        help=FILE_TYPE_HELP_TEXT,
        key="app_filetype",
    )

    files = st.file_uploader(
        "Upload your medical image file here:",
        type=(
            "zip"
            if st.session_state["app_filetype"] == "DICOMDIR"
            else (
                []
                if st.session_state["app_filetype"] == "DICOM"
                else (
                    ["jpg", "zip"]
                    if st.session_state["app_filetype"] == "JPG"
                    else ["png", "zip"]
                )
            )
        ),
        accept_multiple_files=(
            False if st.session_state["app_filetype"] == "DICOMDIR" else True
        ),
        width=300,
    )

    if st.button(
        "Load",
        type="primary",
        icon=":material/update:",
        use_container_width=True,
    ):
        if files is not None:
            with st.spinner("Processing the uploaded file..."):
                try:
                    load_file(files)
                except Exception as ex:
                    del st.session_state["filehandler"]
                    st.sidebar.error(str(ex))
                    st.stop()
            # st.success("File loaded successfully.")
        else:
            st.error("No file selected.")
    st.space()
    # if "filehandler" in st.session_state and st.session_state["filehandler"]:
    #     if st.button(
    #         "Process by AI",
    #         type="primary",
    #         use_container_width=True,
    #         icon=":material/smart_toy:",
    #         disabled=True,
    #     ):
    #         pass


if (
    "app_filetype_loaded" in st.session_state
    and st.session_state["app_filetype_loaded"]
):
    st.session_state["filehandler"] = get_filehandler_class(
        st.session_state["app_filetype_loaded"]
    )
    st.session_state["filehandler"].show()
