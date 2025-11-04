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

st.set_page_config(
    page_title="Vibe Finance Tracker",
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

def save_to_master_file(data_to_save):
    MASTER_FILE = "master_spreadsheet.xlsx"
    
    # 1. Prepare the data
    df = data_to_save.copy()
    
    # 2. Apply Fail-safe
    df['Category'] = df['Category'].fillna('Other').replace('', 'Other')
    
    # 3. Convert 'date' column to datetime objects
    df['date'] = pd.to_datetime(df['date'])
    
    # 4. Create the 'tab_name' column (e.g., "July 2025")
    df['tab_name'] = df['date'].dt.strftime('%B %Y')
    
    # 5. Get a list of unique tabs we need to update
    tabs_to_update = df['tab_name'].unique()
    
    # 6. Check if file exists, or create it
    if not Path(MASTER_FILE).exists():
        # Create a new file with a blank Dashboard
        with pd.ExcelWriter(MASTER_FILE, engine='xlsxwriter') as writer:
            pd.DataFrame().to_excel(writer, sheet_name='Dashboard')
        st.toast(f"Created new {MASTER_FILE}")

    # 7. Load all existing data from the master file
    try:
        with pd.ExcelFile(MASTER_FILE) as xls:
            existing_data = {sheet: pd.read_excel(xls, sheet, index_col=0) for sheet in xls.sheet_names}
    except (InvalidFileException, ValueError, KeyError):
        st.error("Error reading master file. It might be corrupt. Creating a new one.")
        existing_data = {}
        if 'Dashboard' not in existing_data:
             existing_data['Dashboard'] = pd.DataFrame() # Ensure Dashboard exists

    # 8. Loop through each tab we need to update
    for tab_name in tabs_to_update:
        # Get all *new* transactions for this tab
        new_data_for_tab = df[df['tab_name'] == tab_name]
        
        # Pivot the new data
        # index = 'date' (rows)
        # columns = 'Category'
        # values = 'amount' (sum them up)
        new_pivot = new_data_for_tab.pivot_table(
            index='date',
            columns='Category',
            values='amount',
            aggfunc='sum',
            fill_value=0
        )
        
        # 9. Check if we have *old* data for this tab
        if tab_name in existing_data:
            old_pivot = existing_data[tab_name]
            # Combine old and new. This is the "summation" logic!
            combined_pivot = old_pivot.add(new_pivot, fill_value=0)
            existing_data[tab_name] = combined_pivot
        else:
            # This is a brand new tab
            existing_data[tab_name] = new_pivot

    with pd.ExcelWriter(MASTER_FILE, engine='xlsxwriter') as writer:
        workbook = writer.book
        accounting_format = workbook.add_format({'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        for sheet_name, sheet_data in existing_data.items():
            # Ensure the index (date) is formatted nicely
            if isinstance(sheet_data.index, pd.DatetimeIndex):
                sheet_data.index = sheet_data.index.date
            sheet_data.to_excel(writer, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
    
            # Set Column A (the "Date" column) to a width of 12
            worksheet.set_column(0, 0, 12)
            
            # Set Column B to the end to a width of 15 (for Accounting)
            worksheet.set_column(1, len(sheet_data.columns), 15, accounting_format)
    
    return True # Success

# --- SESSION STATE ---
if 'app_step' not in st.session_state:
    st.session_state.app_step = "1_upload" # Tracks our app's current step

if 'ai_progress_index' not in st.session_state:
    st.session_state.ai_progress_index = 0 # Our "bookmark"

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

# --- MAIN APP ---
st.title("My Finance Tracker App")
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

        st.divider() # A nice horizontal line
        st.subheader("Save Your Work")
        st.write("This will save your edited data to `master_spreadsheet.xlsx`")
        
        if st.button("Save to Master File", type="primary"):
            with st.spinner("Saving to master file..."):
                final_data_to_save = st.session_state.processed_data
                if save_to_master_file(final_data_to_save):
                    st.success(f"Successfully saved {len(final_data_to_save)} transactions to `master_spreadsheet.xlsx`!")
                    st.balloons()
                else:
                    st.error("An error occurred while saving.")

        if st.button("Process New Files"):
             # Reset everything
            st.session_state.processed_data = None
            st.session_state.app_step = "1_upload"
            st.session_state.ai_progress_index = 0 # (This one is old, we can remove it)
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
    MASTER_FILE = "master_spreadsheet.xlsx"

    if not Path(MASTER_FILE).exists():
        st.info("Your dashboard is empty. Process some files in the 'Data Processing' tab to see your stats!")
    else:
        try:
            # Load all data
            with pd.ExcelFile(MASTER_FILE) as xls:
                sheet_names = [s for s in xls.sheet_names if s != 'Dashboard']
            
            if not sheet_names:
                st.info("No monthly data found. Process some files to build your dashboard.")
            else:
                all_data_list = [pd.read_excel(MASTER_FILE, sheet_name=sheet, index_col=0) for sheet in sheet_names]
                all_data = pd.concat(all_data_list)
                all_data.fillna(0, inplace=True) # Replace any empty cells with 0
                all_data = all_data * -1

                # --- 1. CALCULATE METRICS ---
                total_spent = all_data.values.sum()
                
                # Sum by category (columns)
                category_totals = all_data.sum(axis=0)
                top_category = category_totals.idxmax()
                top_category_value = category_totals.max()
                
                num_months = len(sheet_names)
                avg_per_month = total_spent / num_months

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
                st.divider() # Adds a nice horizontal line
                st.header("The Spending Pie")
                
                # We already have `category_totals` from the "Headline News"
                # We just need to format it for Altair
                pie_data = category_totals.reset_index(name='Total').rename(columns={'index': 'Category'})
                
                # Build the donut chart
                donut_chart = alt.Chart(pie_data).mark_arc(outerRadius=120, innerRadius=80).encode(
                    # The "slice" size is based on the "Total"
                    theta=alt.Theta("Total:Q", stack=True), 
                    
                    # The "color" is based on the "Category"
                    color=alt.Color("Category:N"),
                    
                    # Order the slices from biggest to smallest
                    order=alt.Order("Total", sort="descending"),
                    
                    # Add a tooltip to show details on hover
                    tooltip=["Category", alt.Tooltip("Total", format="$,.2f")]
                ).properties(
                    title="Spending Breakdown by Category"
                )
                
                st.altair_chart(donut_chart, use_container_width=True)

                # --- 4. DISPLAY "THE FINANCIAL HEARTBEAT" ---
                st.divider() # Adds a nice horizontal line
                st.header("The Financial Heartbeat")
                st.write("Your total spending, month by month.")
                
                # We already have `all_data_list` and `sheet_names`
                # Let's calculate the total for each month
                monthly_totals_list = [sheet.values.sum() * -1 for sheet in all_data_list]
                
                # Create a simple DataFrame for Streamlit's bar chart
                heartbeat_data = pd.DataFrame({
                    'Month': sheet_names,
                    'Total Spend': monthly_totals_list
                })
                
                # Set 'Month' as the index so the chart labels are correct
                heartbeat_data = heartbeat_data.set_index('Month')
                
                st.bar_chart(heartbeat_data, use_container_width=True, color="#00f2c3")
        
        except Exception as e:
            st.error(f"Error reading dashboard file: {e}")
            st.info("The master file might be open or corrupt.")