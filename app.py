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

# --- CUSTOM CSS FOR "GRADIENT GLOW" VIBE ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');

/* This targets the main app background */
.stApp {
    background: radial-gradient(at top left, #1a004f 0%, #0d1117 70%);
    font-family: 'Space Mono', monospace;
}

/* This makes the sidebar match */
.st-emotion-cache-16txtl3 {
    background-color: #0d1117;
    font-family: 'Space Mono', monospace;
}

/* This makes the "cards" for our metrics pop */
.st-emotion-cache-q8sbsg {
    background-color: #161B22;
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


def get_excel_col(col_num):
    """Converts a column number (e.g., 5) into an Excel letter (e.g., 'E')."""
    letter = ''
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter


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
                data['File Name'] = file.name
                all_data.append(data)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

def convert_df_to_excel(new_data_df, existing_file_buffer=None):
    """
    This is our new "Master Chef" (v2.0).
    It builds a "RAW_DATA" sheet and uses *real*
    Excel Pivot Tables to enable the "drill-down" feature.
    """
    output_buffer = BytesIO()
    
    # --- VIBE 1: PREPARE THE "RAW DATA" ---
    df = new_data_df.copy()
    df['Category'] = df['Category'].fillna('Other').replace('', 'Other')
    df['date'] = pd.to_datetime(df['date'])
    
    # This is our new "master list" of all transactions
    raw_data = df
    
    # --- VIBE 2: MERGE WITH EXISTING "RAW DATA" (if it exists) ---
    if existing_file_buffer is not None:
        try:
            existing_file_buffer.seek(0)
            # Try to read the *old* "RAW_DATA" tab
            old_raw_data = pd.read_excel(existing_file_buffer, sheet_name="RAW_DATA", engine='openpyxl')
            # If it works, "vibe-merge" them!
            raw_data = pd.concat([old_raw_data, raw_data], ignore_index=True)
        except Exception as e:
            st.error(f"Error merging files: {e}. Starting fresh.")
            # If it fails, we just use the new data
    
    # --- VIBE 3: PREPARE DATA FOR PIVOT ---
    # We *must* have a real "date" (not "datetime") for the pivot
    raw_data['date'] = raw_data['date'].dt.date
    
    # Create our "Month-Year" sorting column
    raw_data['tab_name'] = pd.to_datetime(raw_data['date']).dt.strftime('%B %Y')
    
    # Get a list of all our unique month-tabs
    tabs_to_create = raw_data['tab_name'].unique()
    
    # --- VExample 4: WRITE TO "IN-MEMORY" FILE ---
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        accounting_format = workbook.add_format({'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        
        # --- A: Write the "BRAIN" (RAW_DATA) tab ---
        raw_data.to_excel(writer, sheet_name="RAW_DATA", index=False)
        # Hide the "brain" (this is a "pro-vibe" move)
        writer.sheets["RAW_DATA"].hide()
        
        # --- B: Create the "SMART PIVOT" tabs ---
        
        # "Vibe-Sort" our tabs (latest month first)
        sorted_month_tabs = sorted(
            tabs_to_create,
            key=lambda d: pd.to_datetime(d, format='%B %Y'),
            reverse=True
        )
        
        for tab_name in sorted_month_tabs:
            # Create a new "vibe" sheet
            worksheet = workbook.add_worksheet(tab_name)
            
            # Add the *real* "Smart" Pivot Table!
            # This "vibe" tells Excel to build a pivot table...
            pivot_table = worksheet.add_pivot_table('A1', {
                'data': f'RAW_DATA!$A$1:${get_excel_col(len(raw_data.columns))}${len(raw_data)+1}',
                'rows': ['date'],
                'columns': ['Category'],
                'values': ['amount'],
                'values_function': 'sum',
                'values_name': 'Total',
                'row_filter': {'field': 'tab_name', 'criteria': tab_name},
                'format': accounting_format
            })
            
            # Set our "vibe" column widths
            worksheet.set_column(0, 0, 12) # Date column
            worksheet.set_column(1, len(raw_data['Category'].unique()), 15) # Money columns

    return output_buffer.getvalue()


@st.cache_data
def load_dashboard_data(uploaded_file):
    """
    This is our "magic" cached function. It reads the
    uploaded Excel file *only once* and returns all
    the data our dashboard needs.
    """
    try:
        # We must "reset" the buffer so pandas can read it
        uploaded_file.seek(0) 
        with pd.ExcelFile(uploaded_file, engine='openpyxl') as xls:
            sheet_names = [s for s in xls.sheet_names if s != '.vibe-check']
        
        if not sheet_names:
            # No data, return empty "vibes"
            return pd.DataFrame(), [], [] 
        
        # We must "reset" the buffer *again* for the *next* read
        uploaded_file.seek(0)
        all_data_list = [pd.read_excel(uploaded_file, sheet_name=sheet, index_col=0, engine='openpyxl') for sheet in sheet_names]
        
        all_data = pd.concat(all_data_list)
        all_data.fillna(0, inplace=True)
        all_data = all_data * -1 # Apply our "Net Spend" vibe
        
        # Return all three things our dashboard needs
        return all_data, sheet_names, all_data_list

    except Exception as e:
        st.error(f"Error reading `{uploaded_file.name}`: {e}")
        st.info("The file might be corrupt or not a valid master file.")
        # Return empty "vibes" on failure
        return pd.DataFrame(), [], []

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





def sync_editor_state():

    """

    This is our "dumb waiter" (on_change callback).

    It force-syncs our "manager's clipboard" (processed_data)

    with our "chef's clipboard" (data_editor), using the

    *correct 5-column blueprint*.

    """

    

    # 1. Get the "chef's" data

    editor_data = st.session_state.data_editor

    

    # 2. Check the "vibe" (this is our "pro-vibe" guard rail)

    if editor_data is not None:

        # Vibe 1: The "chef" has data (even an empty list [])

        st.session_state.processed_data = pd.DataFrame.from_records(

            editor_data,

            columns=["date", "description", "amount", "Category", "File Name"] # The "Master Blueprint"

        )

    else:

        # Vibe 2: The "chef" is confused (state is None).

        st.session_state.processed_data = pd.DataFrame(

            columns=["date", "description", "amount", "Category", "File Name"] # The "Master Blueprint"

        )





# --- SIDEBAR ---
st.sidebar.title("App Settings")
st.sidebar.subheader("Manage Your Categories")
categories_input = st.sidebar.text_area(
    "Enter your categories (one per line):",
    value="Food\nTransport\nRent\nUtilities\nSubscriptions\nEntertainment\nOther",
    height=250
)
st.session_state.categories = [
    category.strip() for category in categories_input.split('\n') if category.strip()
]
st.sidebar.info("Your categories are now saved! The AI and the dropdowns will use this list.")

# --- "CLOUD-VIBE" UPLOADER ---
st.sidebar.divider()
st.sidebar.subheader("Already have a Master File?")
st.sidebar.write("Upload your `master_spreadsheet.xlsx` here to merge new data or view your dashboard.")

uploaded_master = st.sidebar.file_uploader(
    "Upload your 'master_spreadsheet.xlsx'", 
    type="xlsx",
    accept_multiple_files=False,
    key="master_uploader" # Give it a "vibe" key
)

if uploaded_master:
    st.session_state.uploaded_master_file = uploaded_master
    st.sidebar.success(f"Loaded `{uploaded_master.name}`! Go to the 'Dashboard' tab to see your stats.")
# --- END "CLOUD-VIBE" UPLOADER ---

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
                            data['File Name'] = file.name
                        
                        columns_to_keep = ['date', 'description', 'amount', 'File Name']
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
                columns_to_keep = ['date', 'description', 'amount', 'File Name']
                preview_data = data[columns_to_keep].copy()
                preview_data['Category'] = "" # Leave category blank as requested
                
                st.session_state.processed_data = preview_data
                st.session_state.app_step = "4_display"
                st.rerun()
                
        except subprocess.CalledProcessError as e:
            st.error(f"An error occurred while processing: {e.stderr}")
            st.session_state.app_step = "1_upload"

    # --- STEP 4: DISPLAY THE EDITOR ---
    # --- STEP 4: DISPLAY THE EDITOR ---
    if st.session_state.app_step == "4_display" and st.session_state.processed_data is not None:
        st.subheader("Preview, Edit, and Finalize Your Transactions:")
        
        # This is the "pro-vibe" editor.
        # It's "uncontrolled" and uses our "dumb waiter" to sync.
        st.data_editor(
            st.session_state.processed_data, # Read from our "manager's clipboard"
            num_rows="dynamic",
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    "Category",
                    help="Select the transaction category",
                    options=st.session_state.categories,
                    required=True
                ),
                "File Name": st.column_config.Column(
                    "File Name",
                    disabled=True # "Hides" this column from the user
                )
            },
            key="data_editor", # The "chef's" private clipboard
            on_change=sync_editor_state # Our "bulletproof" translator
        )



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
    else:
        # We have a file! Let's call our new "magic" function.
        # This will run *once* and then use the "magic" answer.
        all_data, sheet_names, all_data_list = load_dashboard_data(st.session_state.uploaded_master_file)
        
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
                
                # We NO LONGER re-read the file! We just use our "magic" variables.
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