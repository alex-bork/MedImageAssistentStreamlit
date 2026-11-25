# MedImageAssistent

MedImageAssistent is a Streamlit-based viewer for navigating and reviewing
medical image data. It converts image series into MP4 videos and provides
controls for playback width and contrast.

> [!WARNING]
> This project is a visualization tool, not a diagnostic or clinical decision
> support system. Do not use it as a substitute for a qualified radiologist or
> an officially validated medical report.

## Supported input

- **DICOMDIR**: a ZIP archive containing a `DICOMDIR` file and its referenced
  DICOM data
- **DICOM**: individual DICOM files, or a ZIP archive containing DICOM files
- **JPG/JPEG**: individual files, or a ZIP archive containing JPG/JPEG images
- **PNG**: individual files, or a ZIP archive containing PNG images

For DICOMDIR archives, the application displays patient details, studies,
series, encapsulated PDF attachments, and image sequences grouped by series.

## Features

- Upload and process DICOMDIR, DICOM, JPG/JPEG, and PNG files
- Open encapsulated PDF attachments
- Generate MP4 videos from image sequences
- Adjust video width and contrast
- Reset video settings to their defaults
- Browse source files and organized DICOMDIR metadata

## Requirements

- Windows, Linux, or macOS
- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/) for dependency and environment management

The project dependencies are listed in `pyproject.toml` and locked in
`uv.lock`.

## Installation

Clone the repository, then create the environment and install dependencies:

```powershell
uv sync
```

## Run the application

Start the Streamlit app with:

```powershell
uv run streamlit run app.py
```

Streamlit will print the local URL in the terminal, typically
`http://localhost:8501`.

The repository also includes a VS Code launch configuration named
**Python: Streamlit**, which starts `app.py` with run-on-save hot reload
enabled.

## Using the app

1. Select a file type in the sidebar.
2. Upload the file or ZIP archive. DICOMDIR requires a ZIP archive.
3. Select **Load**.
4. Review the extracted files and video.
5. Use **Video Width**, **Contrast**, or **Reset to Default** to adjust the
   displayed sequence.

For DICOMDIR data, select the patient and study before browsing the available
series and attachments.

## Project structure

```text
app.py                  Streamlit entry point and upload workflow
modules/common.py       Shared types, ZIP handling, and video conversion
modules/dicom.py        Individual DICOM image handling
modules/dicomdir.py     DICOMDIR archive parsing and navigation
modules/jpg.py          JPG/JPEG image handling
modules/png.py          PNG image handling
modules/texts.py        UI help and prompt text
test_data/              Sample medical image archives
pyproject.toml          Project metadata and dependencies
uv.lock                 Reproducible dependency lock file
```

## Privacy and security

Medical images can contain personal and health information. Keep uploaded data
local, restrict access to deployed instances, and avoid committing patient
images or generated patient metadata to source control.


## License

No license is currently specified. Add a license before distributing or
publishing this repository.