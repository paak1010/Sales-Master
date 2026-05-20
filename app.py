import streamlit as st
import pandas as pd
from io import BytesIO
import glob
import os

# ==========================================
# 1. 페이지 테마 및 스타일 설정 (Streamlit 느낌 제거)
# ==========================================
st.set_page_config(
    page_title="Rohto Mentholatum Inventory System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS: 기업용 대시보드 느낌 구현
st.markdown("""
    <style>
    /* 폰트 설정 및 배경색 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    
    .stApp { background-color: #f8f9fa; }
    
    /* 헤더/푸터 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 사이드바 스타일링 */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    
    /* 버튼 스타일링 (멘소래담 브랜드 컬러 느낌) */
    .stButton > button {
        width: 100%;
        background-color: #ffffff;
        color: #006838;
        border: 1px solid #006838;
        border-radius: 4px;
        font-weight: 600;
        transition: 0.3s;
    }
    .stButton > button:hover {
        background-color: #006838;
        color: #ffffff;
    }

    /* 텍스트 스타일 */
    h1 { color: #1a1a1a; font-weight: 800; letter-spacing: -1px; }
    h3 { color: #006838; font-weight: 700; }
    
    /* 데이터프레임 깔끔하게 */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory_Report')
    return output.getvalue()

# --- 🎯 최신 파일 자동 탐색 함수 (GitHub용) ---
def get_latest_stock_file():
    stock_files = glob.glob("Sales_Stock_*.xlsx")
