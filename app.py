import streamlit as st
import pandas as pd
from io import BytesIO

# 1. 페이지 기본 설정
st.set_page_config(page_title="멘소래담 재고 마스터링 시스템 v4", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    /* 테이블 형태로 보기 좋게 만들기 위한 스타일 고정 */
    .reportview-container .main .block-container { max-width: 95%; }
    .stButton > button { width: 100%; background-color: #f0f2f6; color: #31333F; border-radius: 5px; border: 1px solid #d3d3d3; }
    .stButton > button:hover { background-color: #007bff; color: white; border: 1px solid #007bff; }
    .stDownloadButton > button { background-color: #007bff; color: white; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 가용 재고 마스터링 시스템")

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='재고조회결과')
    return output.getvalue()

# --- 🚨 팝업창(모달 새창) 정의 함수 ---
@st.dialog("📋 상세 LOT 및 유효일자 명세")
def show_lot_details(df_detail, product_name):
    st.markdown(f"**품명:** {product_name}")
    st.dataframe(
        df_detail,
        use_container_width=True,
        hide_index=True,
        column_config={
            "잔여일수": st.column_config.ProgressColumn("잔여일수", format="%d 일", min_value=0, max_value=1095),
            "로트별 수량": st.column_config.NumberColumn("로트별 수량", format="%d 개"),
            "유효일자": st.column_config.DateColumn("유효일자 📅")
        }
    )

# 2. 데이터 로드 및 정밀 전처리
@st.cache_data
def load_filtered_data():
    stock_file = "Sales_Stock_260519.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        # --- 1) 데이터 로드 ---
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        # --- 2) 매핑 키 정규화 ---
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        # --- 3) 데이터 병합 (요청하신 필수 열만 추출) ---
        target_cols = ['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']
        mapping_sub = df_channel[target_cols].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        df_merged.drop(columns=['상품코드_key', '제품코드_key'], inplace=True)
        
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수', '합계수량': '수량',
            'Remarks': '특이사항', 'Sales Team': '영업팀', 'Channel': '채널'
        }, inplace=True)

        # --- 4) 가용 재고 기본 필터링 ---
        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[df_merged['로트번호'] != '']
        df_merged = df_merged[df_merged['로트번호'].str.lower() != 'nan']
        df_merged = df_merged[~df_merged['로트번호'].str.contains('폐기', na=False)]
        
        # --- 5) 🚨 피드백 반영: 납품처가 "-"인 데이터 완전 필터링 ---
        df_merged['납품처'] = df_merged['납품처'].fillna('미지정').astype(str).str.strip()
        df_merged = df_merged[df_merged['납품처'] != '-']
        
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['채널'] = df_merged['채널'].fillna('미분류').astype(str).str.strip()
        df_merged['특이사항'] = df_merged['특이사항'].fillna('').astype(str).str.strip()

        # --- 6) 상품바코드 클렌징 ---
        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\.0$', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'[?？]', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.strip()

        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"❌ 데이터 전처리 오류: {e}")
        st.stop()

df_raw = load_filtered_data()

# ==========================================
# 3. 검색 및 필터링 UI
# ==========================================
st.markdown("### 🔍 필터 설정")
col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

with col_f1:
    all_customers = df_raw['납품처'].unique().tolist()
    customer_set = set(part.strip() for c in all_customers for part in str(c).split(',') if part.strip() != '-')
    unique_customers = sorted(list(customer_set))
    selected_customer = st.selectbox("🏢 납품처 선택", ["전체"] + unique_customers)

with col_f2:
    all_teams = df_raw['영업팀'].unique().tolist()
    team_set = set(part.strip() for t in all_teams for part in str(t).split(',') if part.strip() != '-')
    unique_teams = sorted(list(team_set))
    selected_team = st.selectbox("👥 영업팀 선택", ["전체"] + unique_teams)

with col_f3:
    search_q = st.text_input("📝 제품명 또는 제품코드 검색", placeholder="검색어를 입력하세요...")

# 데이터 필터링 적용
df_filtered = df_raw.copy()
if selected_customer != "전체":
    df_filtered = df_filtered[df_filtered['납품처'].str.contains(selected_customer, na=False, regex=False)]
if selected_team != "전체":
    df_filtered = df_filtered[df_filtered['영업팀'].str.contains(selected_team, na=False, regex=False)]
if search_q:
    df_filtered = df_filtered[
        df_filtered['상품명'].str.contains(search_q, case=False, na=False, regex=False) |
        df_filtered['제품코드'].str.contains(search_q, case=False, na=False, regex=False)
    ]

# ==========================================
# 4. 🚨 마스터 테이블 구성 및 버튼 액션 연결
# ==========================================
st.markdown("---")

if not df_filtered.empty:
    # 바코드와 제품코드 기준으로 묶어서 재고 합산 (마스터 테이블 빌드)
    group_cols = ['상품바코드', '제품코드']
    df_main = df_filtered.groupby(group_cols).agg({
        '상품명': 'first', '납품처': 'first', '영업팀': 'first', '채널': 'first', '특이사항': 'first', '수량': 'sum'
    }).reset_index()
    
    df_main.rename(columns={'수량': '총 가용 재고'}, inplace=True)
    
    # 상단 다운로드 버튼 배치
    st.download_button(
        label="📥 현재 필터링된 전체 내역 엑셀 다운로드",
        data=to_excel(df_filtered),
        file_name="가용재고_마스터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown(f"### 📊 요약 재고 현황판 (총 {len(df_main)}개 품목)")
    
    # --- 🚨 행 끝에 버튼이 삽입된 테이블 UI 직접 빌드 ---
    # 테이블 헤더 그리기
    grid_ratio = [1.5, 1.2, 1.2, 1.5, 3.0, 1.2, 2.0, 1.0] # 열 크기 비율 조정
    headers = ['납품처', '영업팀', '채널', '제품코드', '상품명', '총 가용 재고', '비고/특이사항', '상세보기']
    
    header_cols = st.columns(grid_ratio)
    for col, h_name in zip(header_cols, headers):
        col.markdown(f"**{h_name}**")
    st.markdown("<hr style='margin: 5px 0 10px 0; border-top: 2px solid #bbb;'>", unsafe_allow_html=True)
    
    # 데이터 행 반복 출력
    for idx, row in df_main.iterrows():
        row_cols = st.columns(grid_ratio)
        
        row_cols[0].write(row['납품처'])
        row_cols[1].write(row['영업팀'])
        row_cols[2].write(row['채널'])
        row_cols[3].write(row['제품코드'])
        row_cols[4].write(row['상품명'])
        row_cols[5].write(f"{row['총 가용 재고']:,} 개")
        row_cols[6].write(row['특이사항'])
        
        # 🚨 마지막 열에 새창 팝업을 띄우는 버튼 배치
        if row_cols[7].button("🔎 조회", key=f"btn_{idx}"):
            # 버튼을 누른 해당 행의 바코드와 제품코드에 일치하는 세부 로트 정보 추출
            df_detail = df_filtered[
                (df_filtered['상품바코드'] == row['상품바코드']) & 
                (df_filtered['제품코드'] == row['제품코드'])
            ][['로트번호', '유효일자', '잔여일수', '수량']].copy()
            
            df_detail.rename(columns={'수량': '로트별 수량'}, inplace=True)
            
            # 팝업 함수 호출
            show_lot_details(df_detail, row['상품명'])
else:
    st.warning("⚠️ 필터 조건에 부합하는 가용 재고 데이터가 존재하지 않습니다.")
