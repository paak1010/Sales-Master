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

# --- 🎯 최신 파일 자동 탐색 함수 ---
def get_latest_stock_file():
    stock_files = glob.glob("Sales_Stock_*.xlsx")
    if not stock_files:
        return None
    latest_file = sorted(stock_files, reverse=True)[0]
    return latest_file

# 기존 코드: @st.dialog("📋 로트별 상세 재고 명세")
# 👇 아래처럼 뒤에 width="large" 옵션을 추가해 주세요!

# --- 🚨 상세 팝업창 (동일 로트 합산 & 글자 크기 확대) ---
@st.dialog("📋 로트별 상세 재고 명세", width="large")
def show_lot_details(df_detail, product_name):
    # 💡 1. 제품명 텍스트를 훨씬 크고 굵게 변경 (HTML 적용)
    st.markdown(f"<h3 style='font-size: 24px; color: #006838; margin-bottom: 20px;'>📦 {product_name}</h3>", unsafe_allow_html=True)
    
    # 동일한 로트/유효일/잔여일 데이터 합산
    merged_detail = df_detail.groupby(['로트번호', '유효일자', '잔여일수'], dropna=False, as_index=False)['수량'].sum()
    
    # 선입선출 정렬
    merged_detail = merged_detail.sort_values(by='잔여일수').reset_index(drop=True)
    merged_detail.rename(columns={'수량': '합산 수량'}, inplace=True)

    # 💡 2. 표(데이터프레임) 내부 글자 크기 키우기 (Pandas Styler 적용)
    # font-size 수치를 16px에서 18px, 20px 등으로 더 키우실 수도 있습니다.
    styled_df = merged_detail.style.set_properties(**{
        'font-size': '16px',
        'font-weight': '500'
    })

    st.dataframe(
        styled_df, # 일반 df 대신 스타일이 적용된 styled_df를 넣습니다.
        use_container_width=True,
        hide_index=True,
        column_config={
            "잔여일수": st.column_config.ProgressColumn("유통기한 잔여", format="%d일", min_value=0, max_value=1095),
            "합산 수량": st.column_config.NumberColumn("가용 재고", format="%d EA"),
            "유효일자": st.column_config.DateColumn("유효일자")
        }
    )
    st.markdown("<p style='font-size: 14px; color: gray;'>※ 정보(로트/유효일/잔여일)가 완벽히 동일한 데이터는 자동으로 합산 표시됩니다.</p>", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 로드 및 전처리
# ==========================================
@st.cache_data
def load_and_process_data(stock_file):
    mapping_file = "매핑용.xlsx"
    try:
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()
            
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        mapping_sub = df_channel[['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            '합계수량': '수량', 'Remarks': '특이사항', 'Sales Team': '영업팀', 'Channel': '채널'
        }, inplace=True)

        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[(df_merged['로트번호'] != '') & (df_merged['로트번호'].str.lower() != 'nan')]
        df_merged = df_merged[~df_merged['로트번호'].str.contains('폐기', na=False)]
        
        df_merged['납품처'] = df_merged['납품처'].fillna('미지정').astype(str).str.strip()
        df_merged = df_merged[df_merged['납품처'] != '-']
        
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['특이사항'] = df_merged['특이사항'].fillna('').astype(str).str.strip()

        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'[?？]', '', regex=True).str.strip()

        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"데이터 연동 에러: {e}")
        return None

# 앱 실행 (최신 파일 스캔)
latest_file = get_latest_stock_file()
if not latest_file:
    st.error("폴더 내에 Sales_Stock_*.xlsx 파일이 존재하지 않습니다.")
    st.stop()

df_raw = load_and_process_data(latest_file)
if df_raw is None: st.stop()

# ==========================================
# 3. 사이드바 UI (구조 재배치 및 필터 리스트 정제)
# ==========================================
with st.sidebar:
    # 1. 최상단 로고
    if os.path.exists("logo.png"):
        st.image("logo.png", width=200)
    else:
        st.subheader("Mentholatum")
        
    st.markdown("---")
    
    # 2. 필터 옵션 영역
    st.subheader("Filter Option")
    
    is_exclusive = st.toggle("🌟 전용 납품 품목만 보기")
    st.markdown("<div style='border-bottom: 1px solid #eaeaea; margin: 12px 0;'></div>", unsafe_allow_html=True)
    
    # 납품처 리스트 정제 (콤마 분리 후 고유값 추출)
    customer_set = set(part.strip() for c in df_raw['납품처'].dropna() for part in str(c).split(','))
    all_customers = sorted(list(customer_set))
    selected_customer = st.selectbox("🏢 납품처", ["전체"] + all_customers)
    
    st.markdown("<div style='border-bottom: 1px solid #eaeaea; margin: 12px 0;'></div>", unsafe_allow_html=True)
    
    # 영업팀 리스트 정제 (콤마 분리 후 고유값 추출)
    team_set = set(part.strip() for t in df_raw['영업팀'].dropna() for part in str(t).split(','))
    all_teams = sorted(list(team_set))
    selected_team = st.selectbox("👥 영업팀", ["전체"] + all_teams)
    
    st.markdown("<div style='border-bottom: 1px solid #eaeaea; margin: 12px 0;'></div>", unsafe_allow_html=True)
    
    search_q = st.text_input("🔍 Search", placeholder="제품명 또는 코드")
    
    st.markdown("---")
    
    # 3. 관리 정보 영역 (필터 아래로 배치)
    st.subheader("Admin Console")
    st.info(f"📅 **Latest Sync**\n{latest_file}")
    
    st.caption("© 2026 Rohto Mentholatum Korea")

# ==========================================
# 필터링 로직 (Exact Match 적용)
# ==========================================
df_filtered = df_raw.copy()

if is_exclusive:
    df_filtered = df_filtered[~df_filtered['납품처'].astype(str).str.contains(',', na=False)]

if selected_customer != "전체":
    # 정확도 100% 일치 필터링
    df_filtered = df_filtered[
        df_filtered['납품처'].apply(lambda x: selected_customer in [c.strip() for c in str(x).split(',')])
    ]

if selected_team != "전체":
    # 정확도 100% 일치 필터링
    df_filtered = df_filtered[
        df_filtered['영업팀'].apply(lambda x: selected_team in [t.strip() for t in str(x).split(',')])
    ]

if search_q:
    df_filtered = df_filtered[
        df_filtered['상품명'].str.contains(search_q, case=False, na=False) |
        df_filtered['제품코드'].str.contains(search_q, case=False, na=False)
    ]

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
st.title("Inventory Mastering Dashboard")

if not df_filtered.empty:
    df_main = df_filtered.groupby(['상품바코드', '제품코드']).agg({
        '상품명': 'first', '납품처': 'first', '영업팀': 'first', '특이사항': 'first', '수량': 'sum'
    }).reset_index()
    
    df_main.rename(columns={'수량': '총 재고'}, inplace=True)
    
    # 지표 카드
    m1, m2, m3 = st.columns(3)
    m1.metric("총 취급 품목수", f"{len(df_main)} SKUs")
    m2.metric("총 가용 수량", f"{df_main['총 재고'].sum():,} EA")
    with m3:
        st.write(" ")
        st.download_button("📥 Excel Export", data=to_excel(df_filtered), file_name=f"Stock_Report_{latest_file}.xlsx")

    st.markdown("---")
    
    # 테이블 레이아웃
    grid_ratio = [1.5, 1.2, 1.5, 3.5, 1.2, 2.0, 1.0]
    cols = st.columns(grid_ratio)
    fields = ['납품처', '영업팀', '제품코드', '상품명', '현재고', '특이사항', 'Action']
    for col, field in zip(cols, fields):
        col.markdown(f"**{field}**")
    st.markdown("<div style='border-bottom: 2px solid #006838; margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    for idx, row in df_main.iterrows():
        with st.container():
            r_cols = st.columns(grid_ratio)
            r_cols[0].write(row['납품처'])
            r_cols[1].write(row['영업팀'])
            r_cols[2].write(row['제품코드'])
            r_cols[3].write(f"**{row['상품명']}**")
            r_cols[4].write(f"{row['총 재고']:,}")
            r_cols[5].write(f"<small>{row['특이사항']}</small>", unsafe_allow_html=True)
            
            if r_cols[6].button("상세", key=f"v_{idx}"):
                df_detail = df_filtered[
                    (df_filtered['상품바코드'] == row['상품바코드']) & 
                    (df_filtered['제품코드'] == row['제품코드'])
                ][['로트번호', '유효일자', '잔여일수', '수량']]
                show_lot_details(df_detail, row['상품명'])
else:
    st.warning("조회된 재고 데이터가 없습니다.")
