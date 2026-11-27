from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Final, Optional
from uuid import uuid4
from zipfile import ZipFile
import pydicom
import streamlit as st
from .common import (
    VIDEO_CONTRAST,
    VIDEO_FPS,
    VIDEO_WIDTH,
    FileHandler,
    calc_age,
    convert_dicom_to_mp4,
)


class DicomdirFileNotFoundError(Exception):
    def __init__(self):
        super().__init__("DICOMDIR file not found inside ZIP file.")


@dataclass
class Attachment:
    name: str
    type: str
    data: bin


@dataclass
class Series:
    description: str
    date: str
    time: str
    images: list[pydicom.Dataset] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    video: Optional[bytes] = None


@dataclass
class Study:
    description: str
    date: str
    time: str
    series: list[Series]


@dataclass
class Patient:
    id: str
    name: str
    birth_date: str
    sex: str
    age: str
    studies: list[Study]


class DicomdirFileSet:
    filename: str
    load_id: str
    patients: list[Patient]

    def __init__(self, filename: str):
        self.filename = filename
        self.load_id = uuid4().hex
        self.patients = []

    def get_patient_names(self) -> list[str]:
        patient_names = [patient.name for patient in self.patients]
        return patient_names

    def get_patient_info_by_name(self, name: str) -> dict:
        patient = next(
            (patient for patient in self.patients if patient.name == name), None
        )
        if patient:
            return {
                "name": patient.name,
                "id": patient.id,
                "birth_date": patient.birth_date,
                "sex": patient.sex,
                "age": patient.age,
            }
        return {}

    def get_studies_descr_by_name(self, patient_name: str) -> list[str]:
        patient = next(
            (patient for patient in self.patients if patient.name == patient_name), None
        )
        studies = [study.description for study in patient.studies] if patient else []
        print(studies)
        return studies

    def get_attachments(self, name, study_descr) -> dict:
        attachments = {}
        for patient in [patient for patient in self.patients if patient.name == name]:
            for study in [
                study for study in patient.studies if study.description == study_descr
            ]:
                for series in [series for series in study.series]:
                    for attachment in series.attachments:
                        if not getattr(attachments, series.description, None):
                            attachments[series.description] = []
                        attachments[series.description].append(attachment)
        return attachments

    def get_series_by_study_descr(self, patient_name, study_description) -> dict:
        patient = next(
            (patient for patient in self.patients if patient.name == patient_name), None
        )
        study = next(
            (
                study
                for study in patient.studies
                if study.description == study_description
            ),
            None,
        )
        series_dict = {}

        for series in study.series:
            series_dict[series.description] = {
                "images": series.images,
                "video": series.video,
            }

        return series_dict


class DicomdirHandler(FileHandler):

    data: DicomdirFileSet

    @classmethod
    def load(cls, upload) -> None:

        for key in list(st.session_state.keys()):
            if key.startswith("dicomdir"):
                del st.session_state[key]

        with ZipFile(BytesIO(upload.getvalue())) as z:

            # DICOMDIR suchen
            try:
                dicomdir_name = next(
                    name for name in z.namelist() if name.upper().endswith("DICOMDIR")
                )
            except StopIteration as ex:
                raise DicomdirFileNotFoundError()

            dicomdir_directory = dicomdir_name.rpartition("/")[0]

            # DICOMDIR direkt aus RAM lesen
            dicomdir = pydicom.dcmread(BytesIO(z.read(dicomdir_name)))

            st.session_state["dicomdir"] = DicomdirFileSet(upload.name)

            for record in dicomdir.DirectoryRecordSequence:

                if record.DirectoryRecordType == "PATIENT":
                    st.session_state["dicomdir"].patients.append(
                        Patient(
                            name=str(record.get("PatientName", "N/A")).replace(
                                "^", ", "
                            ),
                            id=record.get("PatientID", "N/A"),
                            birth_date=record.get("PatientBirthDate", "N/A"),
                            sex=(
                                "Male"
                                if record.get("PatientSex") == "M"
                                else (
                                    "Female"
                                    if record.get("PatientSex") == "F"
                                    else "Other"
                                )
                            ),
                            age=calc_age(record.get("PatientBirthDate")),
                            studies=[],
                        )
                    )

                if record.DirectoryRecordType == "STUDY":
                    st.session_state["dicomdir"].patients[-1].studies.append(
                        Study(
                            description=record.get("StudyDescription", "N/A"),
                            date=record.get("StudyDate", "N/A"),
                            time=record.get("StudyTime", "N/A"),
                            series=[],
                        )
                    )

                if record.DirectoryRecordType == "SERIES":
                    st.session_state["dicomdir"].patients[-1].studies[-1].series.append(
                        Series(
                            description=record.get("SeriesDescription", "N/A"),
                            date=record.get("SeriesDate", "N/A"),
                            time=record.get("SeriesTime", "N/A"),
                        )
                    )

                if record.DirectoryRecordType == "IMAGE":
                    image_path = "/".join(
                        part
                        for part in (
                            dicomdir_directory,
                            *record.ReferencedFileID,
                        )
                        if part
                    )
                    image = pydicom.dcmread(BytesIO(z.read(image_path)))
                    if getattr(image, "EncapsulatedDocument", None):
                        st.session_state["dicomdir"].patients[-1].studies[-1].series[
                            -1
                        ].attachments.append(
                            Attachment(
                                image.SOPInstanceUID,
                                image.MIMETypeOfEncapsulatedDocument,
                                image.EncapsulatedDocument,
                            )
                        )
                    elif getattr(image, "PixelData", None):
                        st.session_state["dicomdir"].patients[-1].studies[-1].series[
                            -1
                        ].images.append(image)

        cls.__convert_images_to_video()

    @classmethod
    def __convert_images_to_video(cls, contrast=VIDEO_CONTRAST) -> None:
        for p_index, patient in enumerate(st.session_state["dicomdir"].patients):
            for st_index, study in enumerate(
                st.session_state["dicomdir"].patients[p_index].studies
            ):
                for se_index, series in enumerate(
                    st.session_state["dicomdir"]
                    .patients[p_index]
                    .studies[st_index]
                    .series
                ):
                    if series.images:
                        series.video = convert_dicom_to_mp4(
                            series.images,
                            fps=VIDEO_FPS,
                            contrast=contrast,
                        )

    @classmethod
    def __show_attachment(
        cls, patient_name: str, study_descr: str, attachment_key: str
    ):
        attachments = st.session_state["dicomdir"].get_attachments(
            patient_name, study_descr
        )
        attachment = attachments[attachment_key]
        pass

        @st.dialog(f'Attachment "{attachment_key}"', width="medium")
        def show_dialog():
            for item in attachment:
                st.pdf(item.data)

        show_dialog()

    @classmethod
    def __rerender_images_to_video(cls) -> None:
        cls.__convert_images_to_video(st.session_state["dicomdir_video_contrast"])

    @classmethod
    def show(cls) -> None:
        dicomdir = st.session_state["dicomdir"]
        if not hasattr(dicomdir, "load_id"):
            dicomdir.load_id = uuid4().hex

        col1, col2 = st.columns([1, 1])

        with col1:
            with st.container(border=False):
                st.markdown("##### :material/person: Patient", anchors=False)
                with st.container(horizontal=True, vertical_alignment="bottom", gap=5):
                    patient_name = st.selectbox(
                        "Patient",
                        st.session_state["dicomdir"].get_patient_names(),
                        width=300,
                        index=0,
                        key=f"dicomdir_patient_name",
                        label_visibility="collapsed",
                    )
                    with st.popover("", icon=":material/info:"):
                        patient_info = st.session_state[
                            "dicomdir"
                        ].get_patient_info_by_name(patient_name)
                        st.write(f"**ID:** {patient_info.get('id', 'N/A')}")
                        st.write(f"**Name:** {patient_info.get('name', 'N/A')}")
                        bday = patient_info.get("birth_date", "N/A")
                        if bday != "N/A":
                            birth_date = datetime.strptime(str(bday), "%Y%m%d")
                            bday = (
                                f"{birth_date.day}. {birth_date:%B} {birth_date.year}"
                            )
                        st.write(f"**Birth Date:** {bday}")
                        st.write(f"**Gender:** {patient_info.get('sex', 'N/A')}")
                if patient_name:
                    st.markdown("##### :material/experiment: Study", anchors=False)
                    studylist = st.session_state["dicomdir"].get_studies_descr_by_name(
                        patient_name
                    )
                    study_descr = st.selectbox(
                        "Study",
                        studylist,
                        width=300 + 60,
                        key=(
                            f"dicomdir_study_"
                            f"{dicomdir.load_id}_{patient_name}"
                        ),
                        label_visibility="collapsed",
                    )
                    st.markdown("##### :material/settings: Settings", anchors=False)
                    with st.expander(
                        "Video",
                        width=300 + 60,
                    ):
                        st.selectbox(
                            "Video Width",
                            [200, VIDEO_WIDTH, 600, 800],
                            index=1,
                            key="dicomdir_video_width",
                        )
                        st.slider(
                            "Contrast",
                            min_value=0.1,
                            max_value=2.0,
                            value=VIDEO_CONTRAST,
                            step=0.1,
                            key="dicomdir_video_contrast",
                            on_change=cls.__rerender_images_to_video,
                        )
                        st.button(
                            "Reset to Default", on_click=cls.__reset_video_settings
                        )
        with col2:
            if patient_name and study_descr:
                attachments = st.session_state["dicomdir"].get_attachments(
                    patient_name, study_descr
                )

                if attachments:
                    st.markdown(
                        "##### :material/attach_file: Attachments", anchors=False
                    )
                    for attach_key in attachments.keys():
                        st.button(
                            attach_key,
                            icon=":material/news:",
                            type="tertiary",
                            on_click=cls.__show_attachment,
                            args=[patient_name, study_descr, attach_key],
                        )

        st.space()

        series_dict = st.session_state["dicomdir"].get_series_by_study_descr(
            patient_name, study_descr
        )

        with st.container(horizontal=True, gap=20):
            for name, content in series_dict.items():
                if content["video"]:
                    with st.container(border=True, width="content"):
                        if name and name != "N/A":
                            st.markdown(f"##### {name}", anchors=False)
                        st.video(
                            content["video"],
                            width=st.session_state["dicomdir_video_width"],
                            format="video/mp4",
                            start_time=0,
                        )

    @classmethod
    def __reset_video_settings(cls) -> None:
        st.session_state["dicomdir_video_width"] = VIDEO_WIDTH
        st.session_state["dicomdir_video_contrast"] = VIDEO_CONTRAST
        cls.__rerender_images_to_video()

