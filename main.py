import streamlit as st
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
import pandas as pd
from copy import deepcopy
from io import BytesIO

st.set_page_config(page_title="Blank App", layout="wide")

st.title("Audio Requirements Validator")
st.markdown("업로드된 오디오 파일의 속성을 검증하고, 요구사항과 비교하여 결과를 제공합니다. (Verify the attributes of the uploaded audio file, compare them against the requirements, and provide the results.)")

with st.container(border=True):
    st.markdown("##### 사용 방법 (How to use)")
    st.markdown('''1. 파일 요구사항 설정값 선택 (Select the file requirement settings)\n2. Save 버튼 클릭 (Click the Save button)\n3. 오디오 파일 업로드 (Upload audio files)\n4. 결과 확인 (Check the results)''')
    st.markdown("새로운 파일 요구사항 설정 : Reset 버튼 클릭 (New file requirement settings: Click the Reset button)")

if not st.session_state.get("disabled"):
    st.session_state.disabled = False
if not st.session_state.get("start_button_clicked"):
    st.session_state["start_button_clicked"] = False

if not st.session_state.get("required_format"):
    st.session_state["required_format"] = None
if not st.session_state.get("required_channels"):
    st.session_state["required_channels"] = None
if not st.session_state.get("required_sample_rate"):
    st.session_state["required_sample_rate"] = None
if not st.session_state.get("required_bit_depth"):
    st.session_state["required_bit_depth"] = None
if not st.session_state.get("required_noise_floor"):
    st.session_state["required_noise_floor"] = None
if not st.session_state.get("required_stereo_status"):
    st.session_state["required_stereo_status"] = None

# 파일 요구사항 설정 (기존 코드와 동일)
st.sidebar.header("파일 요구사항 설정 (File requirements settings)")
required_format = st.sidebar.selectbox("Format", ["WAV", "MP3", "AAC"], disabled=st.session_state.disabled)
required_channels = st.sidebar.selectbox("Channels", [1, 2], disabled=st.session_state.disabled)
required_sample_rate = st.sidebar.selectbox("Sample Rate (Hz)", [44100, 48000, 96000, 192000], disabled=st.session_state.disabled)
required_bit_depth = st.sidebar.selectbox("Bit Depth", [16, 24, 32, "32 (float)", "64 (float)"], disabled=st.session_state.disabled)
required_noise_floor = st.sidebar.slider("Noise Floor (dBFS)", min_value=-100, max_value=0, value=-60, disabled=st.session_state.disabled)
required_stereo_status = st.sidebar.selectbox(
    "Stereo Status", ["Dual Mono", "Mono", "True Stereo", "Joint Stereo"], disabled=st.session_state.disabled
)
sidebar_col1, sidebar_col2 = st.sidebar.columns(2)
with sidebar_col1:
    required_start_button = st.sidebar.button("Save", key="start_button", use_container_width=True)
with sidebar_col2:
    required_new_button = st.sidebar.button("Reset", key="new_button", use_container_width=True)

if required_start_button:
    st.session_state["required_format"] = required_format
    st.session_state["required_channels"] = required_channels
    st.session_state["required_sample_rate"] = required_sample_rate
    st.session_state["required_bit_depth"] = required_bit_depth
    st.session_state["required_noise_floor"] = required_noise_floor
    st.session_state["required_stereo_status"] = required_stereo_status

    st.session_state["start_button_clicked"] = True
    st.session_state.disabled = True
    st.rerun()
if required_new_button:
    st.session_state["start_button_clicked"] = False
    st.session_state["disabled"] = False
    st.rerun()
    
if st.session_state["start_button_clicked"] == True:
    st.header("1. 파일 업로드 (1. Upload file)", divider="red")
    # 여러 파일 업로드 위젯 (기존 코드와 동일)
    uploaded_files = st.file_uploader(
        "오디오 파일(wav, mp3, aac)을 업로드하세요. (Upload audio files (wav, mp3, aac).)", type=["wav", "mp3", "aac"], accept_multiple_files=True
    )

    # 오디오 처리 Generator 함수
    def process_audio_files_generator(uploaded_files):
        for uploaded_file in uploaded_files:
            # Buffer 객체 얻기
            audio_buffer = BytesIO(uploaded_file.getvalue())

            # 오디오 속성 분석 함수 (buffer 객체 입력으로 수정)
            def get_audio_properties_from_buffer(buffer):
                try:
                    data, samplerate = sf.read(buffer) # soundfile은 buffer 객체에서 읽기 지원
                    bit_depth = 'Unknown'
                    if data.dtype == 'int16':
                        bit_depth = 16
                    elif data.dtype == 'int24':
                        bit_depth == 24
                    elif data.dtype == 'int32':
                        bit_depth = 32
                    elif data.dtype == 'float32':
                        bit_depth = '32 (float)'
                    elif data.dtype == 'float64':
                        bit_depth = '64 (float)'

                    channels = data.shape[1] if len(data.shape) > 1 else 1
                    duration = len(data) / samplerate

                    return {
                        "Sample Rate": samplerate,
                        "Channels": channels,
                        "Bit Depth": bit_depth,
                        "Duration (seconds)": round(duration, 2)
                    }
                except Exception as e: # soundfile 오류 처리 (특히 MP3 파일)
                    return { # 기본적인 정보만 반환 (샘플레이트, 채널 정보는 불확실)
                        "Sample Rate": "Error",
                        "Channels": "Error",
                        "Bit Depth": "Error",
                        "Duration (seconds)": "Error (Processing Failed)"
                    }

            def calculate_noise_floor_from_buffer(buffer, silence_threshold_db=-60, frame_length=2048, hop_length=512):
                try:
                    data, sr = sf.read(buffer)  # 오디오 파일 읽기
                except sf.LibsndfileError as e:
                    print(f"Error reading audio file: {e}")
                    return None

                # 다채널 오디오라면, 모노로 변환 (선택 사항)
                if data.ndim > 1:
                    y = np.mean(data, axis=1)
                else:
                    y = data

                # 프레임 단위로 RMS 계산
                num_frames = (len(y) - frame_length) // hop_length + 1
                rms_values = np.zeros(num_frames)

                for i in range(num_frames):
                    start = i * hop_length
                    end = start + frame_length
                    frame = y[start:end]
                    rms_values[i] = np.sqrt(np.mean(frame**2))

                # dB 스케일로 변환 (무음 구간 찾기 위해)
                epsilon = 1e-12
                rms_db = 20 * np.log10((rms_values / np.max(np.abs(y))) + epsilon)

                # 무음 구간 찾기
                silent_frames = rms_db < silence_threshold_db

                # 무음 구간 RMS 평균 (진폭 스케일) -> dBFS로 변환
                if np.any(silent_frames):
                    noise_floor_rms = np.mean(rms_values[silent_frames])
                    noise_floor_dbfs = 20 * np.log10(noise_floor_rms / np.max(np.abs(y)) + epsilon)
                else:
                    print("Warning: No silent frames found. Using minimum RMS.")
                    noise_floor_rms = np.min(rms_values)
                    noise_floor_dbfs = 20 * np.log10(noise_floor_rms / np.max(np.abs(y)) + epsilon)

                return round(noise_floor_dbfs, 2)


            def check_stereo_status_from_buffer(buffer):
                try:
                    data, _ = sf.read(buffer) # soundfile은 buffer 객체에서 읽기 지원
                    if len(data.shape) == 1:
                        return "Mono"
                    elif np.array_equal(data[:, 0], data[:, 1]):
                        return "Dual Mono"
                    else:
                        return "True Stereo"
                except Exception as e:
                    return f"Unknown (Error) {e}" # 또는 None 등 오류 표시

            # 기본 속성 가져오기 (buffer 객체 전달)
            properties = get_audio_properties_from_buffer(deepcopy(audio_buffer))
            noise_floor_val = calculate_noise_floor_from_buffer(deepcopy(audio_buffer))
            stereo_status = check_stereo_status_from_buffer(deepcopy(audio_buffer))

            # 요구사항과 비교 (기존 코드와 동일, properties 및 검증 값은 buffer 기반 함수에서 얻음)
            matches_format = uploaded_file.name.lower().endswith(required_format.lower())
            matches_channels = properties["Channels"] == required_channels if properties["Channels"] != "Error" else False
            matches_sample_rate = properties["Sample Rate"] == required_sample_rate if properties["Sample Rate"] != "Error" else False
            matches_bit_depth = str(properties["Bit Depth"]) == str(required_bit_depth) if properties["Bit Depth"] != "Error" else False
            matches_noise_floor = noise_floor_val >= required_noise_floor if isinstance(noise_floor_val, (int, float)) else False
            matches_stereo_status = stereo_status == required_stereo_status if stereo_status != "Unknown (Error)" else False

            matches_all = all(
                [
                    matches_format,
                    matches_channels,
                    matches_sample_rate,
                    matches_bit_depth,
                    matches_noise_floor,
                    matches_stereo_status,
                ]
            )

            # 결과 yield (결과 데이터 생성 방식은 기존 코드와 유사)
            yield {
                "Valid": "O" if matches_all else "X",
                "Name": uploaded_file.name,
                "Time (sec)": properties["Duration (seconds)"] if properties["Duration (seconds)"] != "Error (Processing Failed)" else "Error",
                "Format": required_format if matches_format else f"{uploaded_file.name.split('.')[-1].upper()}",
                "Sample Rate": f"{properties['Sample Rate']} Hz" if properties["Sample Rate"] != "Error" else "Error",
                "Bit Depth": properties["Bit Depth"] if properties["Bit Depth"] != "Error" else "Error",
                "Channels": properties["Channels"] if properties["Channels"] != "Error" else "Error",
                "Stereo Status": stereo_status,
                "Noise Floor (dBFS)": noise_floor_val if isinstance(noise_floor_val, (int, float)) else "Error",
            }

    if uploaded_files:
        results = []  # 결과를 저장할 리스트 (generator 결과를 모으기 위해)

        # Generator 함수 호출 및 결과 수집
        for result in process_audio_files_generator(uploaded_files):
            results.append(result)

        # **결과를 표 형태로 출력 (기존 코드와 동일)**
        st.header("2. 파일 검증 결과 (File verification results)", divider="red")
        st.subheader("2.1 결과표 (Results table)", divider="orange")
        df_results = pd.DataFrame(results).reset_index(drop=True)

        def highlight_rows(row):
            green = 'background-color: lightgreen;color: black;'
            red = 'background-color: lightcoral;color: black;'

            if row['Valid'] == "O":
                colors = [green] * 6
            else:
                colors = [
                    green if row["Format"] == st.session_state["required_format"] else red,
                    green if row["Sample Rate"] == f'{st.session_state["required_sample_rate"]} Hz' else red,
                    green if row["Bit Depth"] == str(st.session_state["required_bit_depth"]) else red,
                    green if row["Channels"] == st.session_state["required_channels"] else red,
                    green if row["Stereo Status"] == st.session_state["required_stereo_status"] else red,
                    green if row["Noise Floor (dBFS)"] < st.session_state["required_noise_floor"] else red
                ]
            return [None] * 3 + colors

        styled_df_results = df_results.style.apply(highlight_rows, axis=1).format(precision=2)
        st.table(styled_df_results)

        st.subheader("2.2 미리듣기 및 파형 (Preview and waveform)", divider="orange")
        for idx, uploaded_file in enumerate(uploaded_files):
            # **미리 듣기 (기존 코드와 동일)**
            st.write(f"##### {idx}. {uploaded_file.name}")
            # **노이즈 음파 시각화 (buffer 객체 사용, torchaudio 사용하는 예시)**
            col1, col2 = st.columns([0.3, 0.7], vertical_alignment="center")
            with col1:
                st.audio(uploaded_file)
            with col2:
                try:
                    audio_buffer = BytesIO(uploaded_file.getvalue())
                    data, samplerate = sf.read(audio_buffer)

                    if data.ndim > 1:
                        data = data[:, 0]

                    fig, ax = plt.subplots(figsize=(10, 2))
                    time_axis = np.linspace(0, len(data) / samplerate, num=len(data))
                    ax.plot(time_axis, data, color='royalblue', linewidth=0.7)
                    ax.axhline(y=10**(required_noise_floor/20), color='red', linestyle='--', label="Required Noise Floor")

                    ax.set_xticks(np.arange(0, max(time_axis), step=5))
                    ax.set_title("Waveform with Noise Floor")
                    ax.set_xlabel("Time (seconds)")
                    ax.set_ylabel("Amplitude")
                    ax.legend(loc="upper right")
                    st.pyplot(fig, use_container_width=True)

                except Exception as e:
                    st.error(f"음파 시각화 오류: 음파 시각화 실패. 파일 형식 또는 코덱을 확인하세요. (Audio visualization error: Failed to visualize waveform. Please check the file format or codec.)")
            st.divider()


    else:
        st.info("파일을 업로드하면 결과가 표시됩니다. (The results will be displayed after you upload a file.)")