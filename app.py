import streamlit as st
import subprocess
import tempfile
import pandas as pd
from pathlib import Path
import google.generativeai as genai
from streamlit.column_config import SelectboxColumn
import time # We'll use this for a simple progress bar
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
import xlsxwriter
import altair as alt
from io import BytesIO

st.set_page_config(
    page_title="Woshi's Finance Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR "MODERN & CLEAN" VIBE ---
st.markdown("""
<style>
/* --- 1. THE FONT --- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');

/* --- 2. KEYFRAME ANIMATIONS (Our "Flipbooks") --- */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes subtlePulse {
  0% { box-shadow: 0 0 0 0 rgba(0, 242, 195, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(0, 242, 195, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 242, 195, 0); }
}

/* --- 3. GLOBAL STYLES (The "House") --- */
.stApp {
    background: radial-gradient(at top left, #1a004f 0%, #0d1117 70%);
    font-family: 'Inter', sans-serif;
    animation: fadeIn 0.8s ease-out;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #161B22;
    border-radius: 10px;
    border: 1px solid #2a3038;
}

/* --- 4. COMPONENT-SPECIFIC STYLES (The "Furniture") --- */
[data-testid="stButton"] button[kind="primary"] {
    background-color: #00f2c3;
    color: #0d1117;
    border: none;
    border-radius: 8px;
    transition: background-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
    animation: subtlePulse 2.5s infinite;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #00f2c3;
    box-shadow: 0 0 15px 5px rgba(0, 242, 195, 0.5);
    transform: scale(1.03);
}
[data-testid="stButton"] button[kind="secondary"] {
    border-color: #555;
    color: #fff;
    border-radius: 8px;
    transition: background-color 0.3s ease, border-color 0.3s ease, transform 0.3s ease, color 0.3s ease;
}
[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #00f2c3;
    color: #00f2c3;
    transform: scale(1.03);
}

/* --- 5. NEW SIDEBAR STYLES (Idea 2) --- */
[data-testid="stSidebar"] {
    background-color: #0d1117;
    border-right: 1px solid #2a3038;
    font-family: 'Inter', sans-serif; /* Make sure font matches */
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    border-radius: 8px;
    transition: background-color 0.3s ease;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background-color: #161B22; /* Our "card" color */
}

</style>
""", unsafe_allow_html=True)
# --- END OF CUSTOM CSS ---

def format_time(seconds):
    """Converts seconds into a H:M:S or M:S string."""
    seconds = int(seconds)
    if seconds > 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours}h {minutes}m {seconds}s"
    elif seconds > 60:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


# --- AI CONFIGURATION ---
# Configure the Gemini AI client using our secret key
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
except Exception as e:
    # If the key is missing, show an error in the sidebar
    st.sidebar.error("GEMINI_API_KEY not found in .streamlit/secrets.toml")
    st.stop() # Stop the app if AI can't be loaded

# --- HELPER FUNCTIONS ---
def get_ai_category(description, categories_list):
    """
    Takes a transaction description and a list of categories,
    and asks the Gemini AI to pick the best one.
    """
    category_string = ", ".join(categories_list)
    
    prompt = f"""
    Given the following transaction description: "{description}"
    
    Please classify it into one of the following categories:
    {category_string}
    
    Your response should be *only* the single, best-matching category name
    from that list, and nothing else.
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean the AI's response (remove extra spaces/newlines)
        ai_guess = response.text.strip()
        
        # Final check: if the AI's guess isn't in our list, default to "Other"
        if ai_guess in categories_list:
            return ai_guess
        else:
            return "Other" # A safe fallback
    except Exception as e:
        st.error(f"AI processing failed for: {description}. Error: {e}")
        return "Other" # Return "Other" on failure

def process_files_to_dataframe(uploaded_files):
    all_data = []
    for file in uploaded_files:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            input_pdf_path = temp_dir_path / file.name
            input_pdf_path.write_bytes(file.getvalue())

            command = ["monopoly", str(input_pdf_path), "-o", str(temp_dir_path)]
            subprocess.run(command, check=True, capture_output=True, text=True)

            csv_files = list(temp_dir_path.glob("*.csv"))
            if csv_files:
                data = pd.read_csv(csv_files[0])
                all_data.append(data)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

def convert_df_to_excel(new_data_df, existing_file_buffer=None):
    """
    This is our new "Master Chef" converter.
    - If 'existing_file_buffer' is None, it creates a new file.
    - If 'existing_file_buffer' is provided, it merges the data.
    """
    output_buffer = BytesIO()
    excel_data = {} # This will hold all our sheets

    # --- VIBE 1: MERGE WITH EXISTING FILE ---
    if existing_file_buffer is not None:
        try:
            # We must "reset" the buffer so pandas can read it
            existing_file_buffer.seek(0)
            with pd.ExcelFile(existing_file_buffer, engine='openpyxl') as xls:
                # Load *all* old data
                excel_data = {sheet: pd.read_excel(xls, sheet, index_col=0) for sheet in xls.sheet_names}
        except Exception as e:
            st.error(f"Error reading uploaded master file: {e}")
            excel_data = {} # Start fresh if file is corrupt
    
    # --- VIBE 2: PREPARE NEW DATA ---
    if 'Dashboard' not in excel_data:
         excel_data['Dashboard'] = pd.DataFrame() # Ensure Dashboard exists
    
    df = new_data_df.copy()
    df['Category'] = df['Category'].fillna('Other').replace('', 'Other')
    df['date'] = pd.to_datetime(df['date'])
    df['tab_name'] = df['date'].dt.strftime('%B %Y')
    tabs_to_update = df['tab_name'].unique()

    # --- VIBE 3: MERGE/ADD NEW DATA ---
    for tab_name in tabs_to_update:
        new_data_for_tab = df[df['tab_name'] == tab_name]
        new_pivot = new_data_for_tab.pivot_table(
            index='date',
            columns='Category',
            values='amount',
            aggfunc='sum',
            fill_value=0
        )
        
        if tab_name in excel_data:
            # Merge Vibe: Add new data to old data
            old_pivot = excel_data[tab_name]
            combined_pivot = old_pivot.add(new_pivot, fill_value=0)
            excel_data[tab_name] = combined_pivot
        else:
            # New Tab Vibe: Just add the new data
            excel_data[tab_name] = new_pivot

    # --- VIBE 4: WRITE TO "IN-MEMORY" FILE ---
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        accounting_format = workbook.add_format({'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        
        for sheet_name, sheet_data in excel_data.items():
            if isinstance(sheet_data.index, pd.DatetimeIndex):
                sheet_data.index = sheet_data.index.date
            sheet_data.to_excel(writer, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
    
            worksheet.set_column(0, 0, 12) # Date column
            worksheet.set_column(1, len(sheet_data.columns), 15, accounting_format) # Money columns

    return output_buffer.getvalue() # Return the "in-memory" file

# --- SESSION STATE ---
if 'app_step' not in st.session_state:
    st.session_state.app_step = "1_upload" # Tracks our app's current step

if 'stop_ai' not in st.session_state:
    st.session_state.stop_ai = False # Our "emergency brake"

if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

if 'categories' not in st.session_state:
    st.session_state.categories = []

if 'all_processed_data' not in st.session_state:
    st.session_state.all_processed_data = [] # Stores *completed* file data

if 'file_progress_index' not in st.session_state:
    st.session_state.file_progress_index = 0 # Bookmark for *which file*

if 'row_progress_index' not in st.session_state:
    st.session_state.row_progress_index = 0 # Bookmark for *which row*

if 'current_file_data' not in st.session_state:
    st.session_state.current_file_data = None

if 'uploaded_master_file' not in st.session_state:
    st.session_state.uploaded_master_file = None




# --- SIDEBAR ---
st.sidebar.title("App Controls")

# --- VIBE 1: FILE MANAGEMENT (Conditional) ---
st.sidebar.subheader("📁 File Management")

# This is our "Conditional UI" (Idea 3)
# Only show the uploader if we are on Step 1 (Upload) or Step 4 (Display)
# When we are in Step 2 (Confirm) or 3 (Processing), it's hidden!
if st.session_state.app_step in ["1_upload", "4_display"]:

    st.sidebar.write("Upload your master file to merge new data or view your dashboard.")
    
    uploaded_master = st.sidebar.file_uploader(
        "Upload 'master_spreadsheet.xlsx'", 
        type="xlsx",
        accept_multiple_files=False,
        key="master_uploader"
    )
    
    if uploaded_master:
        st.session_state.uploaded_master_file = uploaded_master
        st.sidebar.success(f"Loaded `{uploaded_master.name}`!")

else:
    # When processing, just show a "locked" message
    st.sidebar.info("Processing new files... File management is disabled.")

st.sidebar.divider()

# --- VIBE 2: APP SETTINGS (in an expander) (Idea 1) ---
with st.sidebar.expander("⚙️ Manage Categories"):
    categories_input = st.text_area(
        "Enter your categories (one per line):",
        value="Food\nTransport\nRent\nUtilities\nSubscriptions\nEntertainment\nOther",
        height=250
    )
    st.session_state.categories = [
        category.strip() for category in categories_input.split('\n') if category.strip()
    ]
    st.info("Your categories are now saved!")

# --- MAIN APP ---
st.title("Woshi's Tracker App")
tab1, tab2 = st.tabs(["🗃️ Data Processing", "📊 Dashboard"])

with tab1:
    st.write("Welcome to my app! Let's get those finances organized.")
    uploaded_files = st.file_uploader("Upload your PDF bank statements here:", accept_multiple_files=True, type="pdf")



    # --- STEP 1: SHOW THE "PROCESS" BUTTON ---
    if uploaded_files and st.session_state.app_step == "1_upload":
        if st.button("Process Uploaded File(s)"):
            st.session_state.app_step = "2_confirm_ai"
            st.rerun() # Rerun the script to show the next step

    # --- STEP 2: SHOW THE "AI CHOICE" ---
    if st.session_state.app_step == "2_confirm_ai":
        st.subheader("Use AI to categorize transactions?")
        st.write("This can take several minutes depending on your API quota.")
        
        col1, col2 = st.columns(2)
        
        if col1.button("✅ Yes, use AI", type="primary"):
            st.session_state.app_step = "3_process_with_ai"
            st.session_state.stop_ai = False # Ensure brake is off
            
            # --- RESET BOOKMARKS FOR NEW JOB ---
            st.session_state.all_processed_data = [] 
            st.session_state.file_progress_index = 0
            st.session_state.row_progress_index = 0
            # --- END RESET ---
            
            st.rerun()

        if col2.button("Skip (I'll categorize manually)"):
            st.session_state.app_step = "3_process_no_ai"
            st.rerun()

    # --- STEP 3A: PROCESS *WITH* AI (FIXED STATE LOGIC) ---
    if st.session_state.app_step == "3_process_with_ai":
        
        eta_placeholder = st.empty()
        row_timer_placeholder = st.empty()
        progress_bar = st.progress(0, text="Starting AI process...")
        
        if st.button("Stop AI ⏹️"):
            st.session_state.stop_ai = True
            st.warning("Stopping AI... Will process remaining files without categorization.")
            time.sleep(1) 
            st.rerun() 

        try:
            total_files = len(uploaded_files)
            
            # Get our "file" bookmark
            file_bookmark = st.session_state.file_progress_index
            
            # --- OUTER (File-by-File) Loop ---
            for i, file in enumerate(uploaded_files[file_bookmark:]):
                
                current_file_index = i + file_bookmark
                
                # --- 1. GET THE *CORRECT* FILE DATA FIRST ---
                if st.session_state.row_progress_index == 0: 
                    with st.spinner(f"Processing `{file.name}` ({current_file_index+1}/{total_files})..."):
                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_dir_path = Path(temp_dir)
                            input_pdf_path = temp_dir_path / file.name
                            input_pdf_path.write_bytes(file.getvalue())

                            command = ["monopoly", str(input_pdf_path), "-o", str(temp_dir_path)]
                            subprocess.run(command, check=True, capture_output=True, text=True)

                            csv_files = list(temp_dir_path.glob("*.csv"))
                            if not csv_files:
                                st.warning(f"Could not find CSV for {file.name}, skipping.")
                                st.session_state.file_progress_index = current_file_index + 1
                                continue # Skip to the next file
                                
                            data = pd.read_csv(csv_files[0])
                        
                        columns_to_keep = ['date', 'description', 'amount']
                        preview_data = data[columns_to_keep].copy()
                        preview_data['Category'] = "" # Start with blank
                        st.session_state.current_file_data = preview_data 
                else:
                    preview_data = st.session_state.current_file_data

                # --- 2. Run the AI Loop (if "Stop" is not pressed) ---
                num_rows = len(preview_data)
                time_per_row = 4.1 
                row_bookmark = st.session_state.row_progress_index

                for index, row in preview_data.iloc[row_bookmark:].iterrows():
                    
                    # --- THIS IS THE *ONLY* STOP CHECK ---
                    if st.session_state.stop_ai:
                        break # Stop this *inner* AI loop
                    
                    # (Timers)
                    rows_left = num_rows - st.session_state.row_progress_index
                    total_eta_seconds = rows_left * time_per_row
                    eta_text = format_time(total_eta_seconds)
                    eta_placeholder.markdown(f"#### Processing `{file.name}` ({current_file_index+1}/{total_files})")
                    progress_bar.progress((st.session_state.row_progress_index + 1) / num_rows, text=f"Est. Time Remaining: {eta_text}")
                    
                    guess = get_ai_category(row['description'], st.session_state.categories)
                    preview_data.at[index, 'Category'] = guess
                    st.session_state.current_file_data = preview_data
                    
                    # (Row Countdown Timer)
                    for t in range(int(time_per_row), 0, -1):
                        row_timer_placeholder.info(f"Categorizing: `{row['description'][:30]}...` (Waiting for quota... {t}s)")
                        time.sleep(1)
                    time.sleep(time_per_row - int(time_per_row))
                    
                    st.session_state.row_progress_index = preview_data.index.get_loc(index) + 1

                # --- 3. After the *inner* loop (file is done or stopped) ---
                st.session_state.all_processed_data.append(st.session_state.current_file_data)
                st.session_state.file_progress_index = current_file_index + 1
                st.session_state.row_progress_index = 0
                st.session_state.current_file_data = None 

            # --- 4. Finalize (After *outer* loop) ---
            eta_placeholder.empty()
            row_timer_placeholder.empty()
            progress_bar.empty()
            
            if not st.session_state.all_processed_data:
                st.error("No data was processed.")
                st.session_state.app_step = "1_upload"
            else:
                final_data = pd.concat(st.session_state.all_processed_data, ignore_index=True)
                st.session_state.processed_data = final_data
                st.success("Processing complete! (AI was stopped early)") if st.session_state.stop_ai else st.success("AI categorization complete!")
                st.session_state.app_step = "4_display"

            # Reset bookmarks for the *next* full job
            st.session_state.file_progress_index = 0
            st.session_state.row_progress_index = 0
            st.session_state.stop_ai = False
            st.session_state.all_processed_data = []
            st.session_state.current_file_data = None
            st.rerun()

        except subprocess.CalledProcessError as e:
            st.error(f"An error occurred while processing: {e.stderr}")
            # Reset everything on failure
            st.session_state.app_step = "1_upload"
            st.session_state.processed_data = None
            st.session_state.file_progress_index = 0
            st.session_state.row_progress_index = 0
            st.session_state.all_processed_data = []
            st.session_state.current_file_data = None

    # --- STEP 3B: PROCESS *WITHOUT* AI ---
    if st.session_state.app_step == "3_process_no_ai":
        try:
            with st.spinner("Processing files (skipping AI)..."):
                data = process_files_to_dataframe(uploaded_files)
            
            if data is not None:
                st.success("Files processed! Skipping AI categorization.")
                columns_to_keep = ['date', 'description', 'amount']
                preview_data = data[columns_to_keep].copy()
                preview_data['Category'] = "" # Leave category blank as requested
                
                st.session_state.processed_data = preview_data
                st.session_state.app_step = "4_display"
                st.rerun()
                
        except subprocess.CalledProcessError as e:
            st.error(f"An error occurred while processing: {e.stderr}")
            st.session_state.app_step = "1_upload"

    # --- STEP 4: DISPLAY THE EDITOR ---
    if st.session_state.app_step == "4_display" and st.session_state.processed_data is not None:
        st.subheader("Preview, Edit, and Finalize Your Transactions:")
        
        # --- This is the new, simple, "vibe-approved" editor ---
    
        # 1. Read the data from the "magic whiteboard"
        data_for_editor = st.session_state.processed_data 
        
        # 2. Give that data to the "dumb" editor and get back its new state
        configured_editor = st.data_editor(
            data_for_editor,  # Use the data we just read
            num_rows="dynamic",
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    "Category",
                    help="Select the transaction category",
                    options=st.session_state.categories,
                    required=True
                )
            }
            # Note: NO "key=" and NO "on_change=" !!
        )
        
        # 3. Save the *returned* data right back to the "magic whiteboard"
        st.session_state.processed_data = configured_editor



        # --- NEW "CLOUD-VIBE" DOWNLOAD SECTION (FINAL) ---
        st.divider()
        st.subheader("Your Data is Ready!")
        st.write("You can now download your processed transactions.")
        
        # Get our "magic whiteboard" data
        final_data_to_save = st.session_state.processed_data
        
        col1, col2 = st.columns(2)

        # --- Button 1: Download as New ---
        with col1:
            # Call the "Master Chef" with *only* new data
            excel_data_new = convert_df_to_excel(final_data_to_save, existing_file_buffer=None)
            
            st.download_button(
                label="Download as New Spreadsheet",
                data=excel_data_new,
                file_name="master_spreadsheet_new.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        # --- Button 2: Merge & Download ---
        with col2:
            # First, check if a file is uploaded
            uploaded_file = st.session_state.uploaded_master_file
            
            if uploaded_file:
                # Call the "Master Chef" with *both* new data and the old file
                excel_data_merged = convert_df_to_excel(final_data_to_save, existing_file_buffer=uploaded_file)
                
                st.download_button(
                    label="Merge & Download",
                    data=excel_data_merged,
                    file_name="master_spreadsheet_merged.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                # If no file, show a "disabled" vibe
                st.button("Merge with Uploaded Master", disabled=True, help="Please upload a 'master_spreadsheet.xlsx' to enable merging.")

        if st.button("Process New Files"):
             # Reset everything
            st.session_state.processed_data = None
            st.session_state.app_step = "1_upload"
            st.session_state.stop_ai = False
            
            # --- ADD THESE RESETS ---
            st.session_state.all_processed_data = []
            st.session_state.file_progress_index = 0
            st.session_state.row_progress_index = 0
            st.session_state.current_file_data = None
            # --- END OF RESETS ---
            
            st.rerun()

with tab2:
    st.subheader("My Financial Dashboard")
    
    # --- NEW "CLOUD-VIBE" LOGIC (No "Bouncer") ---
    if st.session_state.uploaded_master_file is None:
        st.info("Upload your 'master_spreadsheet.xlsx' in the 'Data Processing' tab to see your dashboard.")
        all_data = pd.DataFrame() 
        sheet_names = []

    else:
        # We have a file! Let's *try* to read it.
        uploaded_file = st.session_state.uploaded_master_file
        uploaded_file.seek(0) # Reset buffer
        
        try:
            st.success(f"Dashboard loaded from `{uploaded_file.name}`!")
            # Load all data from the *uploaded file*
            with pd.ExcelFile(uploaded_file, engine='openpyxl') as xls:
                sheet_names = [s for s in xls.sheet_names if s not in ['Dashboard', '.vibe-check']]
            
            if not sheet_names:
                st.info("Your master file doesn't have any monthly data yet.")
                all_data = pd.DataFrame()
            else:
                uploaded_file.seek(0)
                all_data_list = [pd.read_excel(uploaded_file, sheet_name=sheet, index_col=0, engine='openpyxl') for sheet in sheet_names]
                all_data = pd.concat(all_data_list)
                all_data.fillna(0, inplace=True)
                all_data = all_data * -1 # Apply our "Net Spend" vibe

        except Exception as e:
            st.error(f"Error reading `{uploaded_file.name}`: {e}")
            st.info("The file might be corrupt, not an Excel file, or not a valid master file.")
            all_data = pd.DataFrame()
            sheet_names = []

    # --- ALL OUR "VIBE" CHARTS ---
    if not all_data.empty:
        # (All our chart logic... it's all the same!)
        # --- 1. CALCULATE METRICS ---
        total_spent = all_data.values.sum()
        category_totals = all_data.sum(axis=0)
        top_category = category_totals.idxmax()
        top_category_value = category_totals.max()
        num_months = len(sheet_names)
        avg_per_month = total_spent / num_months if num_months > 0 else 0

        # --- 2. DISPLAY "HEADLINE NEWS" METRICS ---
        st.header("Headline News")
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.metric("Total Recorded Spend", f"${total_spent:,.2f}")
        with col2:
            with st.container(border=True):
                st.metric(f"Top Category: {top_category}", f"${top_category_value:,.2f}")
        with col3:
            with st.container(border=True):
                st.metric("Avg. Monthly Spend", f"${avg_per_month:,.2f}")

        # --- 3. DISPLAY "THE SPENDING PIE" ---
        st.divider()
        st.header("The Spending Pie")
        colA, colB = st.columns(2)
        with colA:
            pie_data = category_totals.reset_index(name='Total').rename(columns={'index': 'Category'})
            donut_chart = alt.Chart(pie_data).mark_arc(outerRadius=120, innerRadius=80).encode(
                theta=alt.Theta("Total:Q", stack=True), 
                color=alt.Color("Category:N"),
                order=alt.Order("Total", sort="descending"),
                tooltip=["Category", alt.Tooltip("Total", format="$,.2f")]
            ).properties(title="Spending Breakdown by Category")
            st.altair_chart(donut_chart, use_container_width=True)

        # --- 4. DISPLAY "THE FINANCIAL HEARTBEAT" ---
        with colB:
            st.header("The Financial Heartbeat")
            st.write("Your total spending, month by month.")
            
            uploaded_file.seek(0)
            all_data_list = [pd.read_excel(uploaded_file, sheet_name=sheet, index_col=0, engine='openpyxl') for sheet in sheet_names]
            
            monthly_totals_list = [sheet.values.sum() * -1 for sheet in all_data_list]
            heartbeat_data = pd.DataFrame({'Month': sheet_names, 'Total Spend': monthly_totals_list})
            heartbeat_data = heartbeat_data.set_index('Month')
            st.bar_chart(heartbeat_data, use_container_width=True, color="#00f2c3")
    else:
        if st.session_state.uploaded_master_file is not None:
            # This catches the case where the file was *bad*
            st.warning("Could not read any data from the uploaded file.")
        else:
            # This is the normal "empty" state
            st.info("Your dashboard is empty.")