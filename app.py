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

st.markdown(
    """
    <style>
    /* Target the sidebar */
    section[data-testid="stSidebar"] {
        /* The "frosted glass" effect */
        backdrop-filter: blur(10px);
        
        /* Make the background semi-transparent.
        You might need to adjust this color to match your dark theme!
        This is a dark gray with 30% opacity. 
        */
        background-color: rgba(40, 40, 40, 0.3);
        
        /* A subtle border to define the edge of the glass */
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Optional: Make the sidebar text slightly brighter */
    section[data-testid="stSidebar"] * {
        color: #FFFFFF; 
    }

    /* Target Streamlit's main button element */
    [data-testid="stButton"] > button {
        /* This is the secret sauce: makes all changes smooth */
        transition: transform 0.15s ease-out, background-color 0.15s ease-out;
        
        /* Set a default state */
        transform: scale(1.0);
    }

    /* This is when the user's mouse is hovering over the button */
    [data-testid="stButton"] > button:hover {
        /* Make the button slightly "lift up" */
        transform: scale(1.03);
        /* You can also add other effects, like a slight brightness change */
        filter: brightness(1.1);
    }

    /* This is when the user is actively clicking the button */
    [data-testid="stButton"] > button:active {
        /* Make the button "press down" */
        transform: scale(0.98);
        /* Make it look more "pressed" */
        filter: brightness(0.9);
    }
    </style>
    """,
    unsafe_allow_html=True
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

# --- NEW MASTER "CHEF" FUNCTION (v1.4.0) ---
def convert_df_to_excel(new_data_df, existing_file_buffer=None):
    """
    This is the new v1.4.0 "Master Chef" converter.
    - It creates a master "Expenses" sheet (raw data).
    - It creates/preserves "Income" sheets for manual entry.
    - It creates "Overview" sheets with budget calculations.
    """
    output_buffer = BytesIO()
    
    preserved_sheets = {
        'Income': pd.DataFrame(columns=['Date', 'Income Source', 'Amount', 'Notes']),
        'Income Dashboard': pd.DataFrame()
    }
    df_expenses_master = pd.DataFrame()

    # --- VIBE 1: MERGE (If user uploaded a file) ---
    if existing_file_buffer is not None:
        try:
            existing_file_buffer.seek(0)
            with pd.ExcelFile(existing_file_buffer, engine='openpyxl') as xls:
                if 'Income' in xls.sheet_names:
                    preserved_sheets['Income'] = pd.read_excel(xls, 'Income')
                if 'Income Dashboard' in xls.sheet_names:
                    preserved_sheets['Income Dashboard'] = pd.read_excel(xls, 'Income Dashboard')
                if 'Expenses' in xls.sheet_names:
                    df_expenses_master = pd.read_excel(xls, 'Expenses')
        except Exception as e:
            st.error(f"Error reading uploaded master file: {e}")
            # Start fresh if file is corrupt
            df_expenses_master = pd.DataFrame()
            preserved_sheets['Income'] = pd.DataFrame(columns=['Date', 'Income Source', 'Amount', 'Notes'])

    # --- VIBE 2: COMBINE & SORT EXPENSES ---
    # Clean up categories before merging
    new_data_df['Category'] = new_data_df['Category'].fillna('Other')
    new_data_df['Category'] = new_data_df['Category'].replace('', 'Other')
    df_expenses_master = pd.concat([df_expenses_master, new_data_df], ignore_index=True)
    df_expenses_master['date'] = pd.to_datetime(df_expenses_master['date'])
    df_expenses_master.sort_values(by='date', ascending=True, inplace=True)
    
    # Drop duplicates
    df_expenses_master.drop_duplicates(subset=['date', 'description', 'amount'], keep='last', inplace=True)

    # --- VIBE 3: BUILD THE OVERVIEW SHEETS ---
    
    # 1. Create the 'Month' column (e.g., "2025-11") for pivoting
    df_expenses_master['Month'] = pd.to_datetime(df_expenses_master['date']).dt.strftime('%B %Y')
    
    # 2. Create the pivot table for "Actual" spend
    df_monthly_pivot = df_expenses_master.pivot_table(
        index='Month',
        columns='Category',
        values='amount',
        aggfunc='sum',
        fill_value=0
    )
    df_monthly_pivot = df_monthly_pivot * -1 # Invert values
    
    # 3. Add our new Budget columns to this pivot table
    df_monthly_overview = df_monthly_pivot.copy()


    # (We will add Weekly, Daily, etc. in a later task)

    # --- VIBE 4: WRITE TO "IN-MEMORY" FILE ---
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # --- DEFINE ALL FORMATS FIRST ---
        accounting_format = workbook.add_format({'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        
        # --- 1. Write the sheets in the new, correct order ---
        # (This order defines the tabs from left to right)
        
        # Write Overview sheet FIRST
        df_monthly_overview.to_excel(writer, sheet_name='Monthly Overview')
        
        # Write preserved manual sheets
        preserved_sheets['Income Dashboard'].to_excel(writer, sheet_name='Income Dashboard', index=False)
        preserved_sheets['Income'].to_excel(writer, sheet_name='Income', index=False)
        
        # Write Expenses sheet LAST
        df_expenses_master.to_excel(writer, sheet_name='Expenses', index=False)

        # --- 2. Add Formatting & Final Touches ---
        
        # --- Monthly Overview Formatting ---
        worksheet_mo = writer.sheets['Monthly Overview']
        
        # --- 4. Color the Monthly Overview Headers ---
        
        # Define our pastel colors
        pastel_colors = [
            '#E0F7FA', '#E8F5E9', '#FFFDE7', '#FCE4EC',
            '#F3E5F5', '#E8EAF6', '#E3F2FD', '#E0F2F1'
        ]
        
        # Get the category column headers (e.g., ['Food', 'Transport', ...])
        # We start from column 1 (B)
        category_headers = df_monthly_overview.columns
        
        for col_num, category_name in enumerate(category_headers, start=1):
            # Pick a color from our list (and "wrap around" if we run out)
            color = pastel_colors[col_num % len(pastel_colors)]
            
            # Create a new format for this header
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': color,
                'border': 1
            })
            
            # Write the header back onto the sheet with the new format
            worksheet_mo.write(0, col_num, category_name, header_format)

        # --- Expenses Sheet Formatting ---
        worksheet_ex = writer.sheets['Expenses']
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        worksheet_ex.set_column('A:A', 12, date_format) # Date
        worksheet_ex.set_column('B:B', 40) # Description
        worksheet_ex.set_column('C:C', 18, accounting_format) # Amount
        worksheet_ex.set_column('D:D', 20) # Category
        worksheet_ex.set_column('E:E', 12) # Month
        
        # --- Income Sheet Formatting ---
        worksheet_in = writer.sheets['Income']
        worksheet_in.set_column('A:A', 12) # Date
        worksheet_in.set_column('B:B', 25) # Income Source
        worksheet_in.set_column('C:C', 18, accounting_format) # Amount
        worksheet_in.set_column('D:D', 40) # Notes
        
        # --- Add Summary Rows (The new logic) ---
        # Get the number of rows of data (e.g., 12 months) + 1 for the header
        num_data_rows = len(df_monthly_overview) + 1
        # Get the number of columns of data (e.g., 5 categories)
        num_data_cols = len(df_monthly_overview.columns)
        
        # Add a blank spacer row
        spacer_row = num_data_rows + 1
        
        # Define summary row numbers
        actual_row = spacer_row + 1
        budget_row = actual_row + 1
        
        # --- Write Summary Row Headers ---
        bold_format = workbook.add_format({'bold': True})
        worksheet_mo.write(actual_row, 0, 'Total Actual', bold_format)
        worksheet_mo.write(budget_row, 0, 'Budget', bold_format)
        
        # --- Write Summary Row Formulas (for each category column) ---
        # Loop from the 2nd column (index 1) to the end
        for col_num in range(1, num_data_cols + 1):
            col_letter = xlsxwriter.utility.xl_col_to_name(col_num)
            
            # 1. Total Actual: =SUM({col_letter}2:{col_letter}{num_data_rows})
            actual_formula = f'=SUM({col_letter}2:{col_letter}{num_data_rows})'
            worksheet_mo.write(actual_row, col_num, actual_formula, accounting_format)
            
            # 2. Budget: =0 (our fail-safe)
            worksheet_mo.write(budget_row, col_num, 0, accounting_format)

        # --- Add NEW Conditional Formatting (Per-Cell) ---
        red_format = workbook.add_format({
            'bg_color': '#FFC7CE',   # Light red fill
            'font_color': '#9C0006' # Dark red text
        })
        
        # Get the range of the main data (e.g., 'B2:F13')
        start_col_letter = xlsxwriter.utility.xl_col_to_name(1)
        end_col_letter = xlsxwriter.utility.xl_col_to_name(num_data_cols)
        data_range = f'{start_col_letter}2:{end_col_letter}{num_data_rows}'
        
        # Get the *first* cell of the budget row (e.g., 'B15')
        # The $ locks the row, so B2 compares to B$15, C2 compares to C$15
        # (budget_row is the variable from our existing code)
        budget_cell_locked = f'{start_col_letter}${budget_row + 1}'
        
        # Apply the format: "Highlight if cell value > its column's budget"
        worksheet_mo.conditional_format(data_range,
            {
                'type': 'formula',
                # The criteria is '=B2>B$15'
                # Excel will automatically adjust 'B2' for each cell in the range,
                # but 'B$15' will "lock" to the correct budget row.
                'criteria': f'={start_col_letter}2>{budget_cell_locked}',
                'format': red_format
            }
        )

        # --- 4. Add formatting for numbers (Vibe Check) ---
        # accounting_format is already defined at the top of the with block

        worksheet_mo.set_column(0, 0, 20) # Widen the 'Month' / Summary header column
        worksheet_mo.set_column(1, num_data_cols, 18, accounting_format)

    # --- VIBE 5: RETURN THE "IN-MEMORY" FILE ---
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

        # 1. READ (The "Security Guard" takes a snapshot)
        # We *must* make a copy for our "before" snapshot
        data_from_state = st.session_state.processed_data.copy()

        # 2. RENDER (Show the editor)
        configured_editor = st.data_editor(
            data_from_state, # Pass in the snapshot
            num_rows="dynamic",
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    "Category",
                    help="Select the transaction category",
                    options=st.session_state.categories,
                    required=True
                )
            },
            key="final_editor" # Keep the key to anchor the widget
        )

        # 3. WRITE (Save the "after" snapshot to the Magic Whiteboard)
        st.session_state.processed_data = configured_editor

        # 4. COMPARE & REFRESH (The "Security Guard" part)
        # Use pandas .equals() to see if *any* data changed.
        if not data_from_state.equals(configured_editor):
            # If the data is different (an edit was made)...
            # ...force a refresh, just like the user suggested!
            st.rerun()



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
    
    # --- NEW v1.4.0 "CLOUD-VIBE" LOGIC ---
    if st.session_state.uploaded_master_file is None:
        st.info("Upload your 'master_spreadsheet.xlsx' in the 'Data Processing' tab to see your dashboard.")
        all_data = pd.DataFrame() 

    else:
        # We have a file! Let's *try* to read *only* the 'Expenses' sheet.
        uploaded_file = st.session_state.uploaded_master_file
        uploaded_file.seek(0) # Reset buffer
        
        try:
            st.success(f"Dashboard loaded from `{uploaded_file.name}`!")
            # Load *only* the 'Expenses' sheet for our dashboard data
            all_data = pd.read_excel(uploaded_file, sheet_name="Expenses", engine='openpyxl')
            
            # Ensure 'amount' is numeric, just in case
            all_data['amount'] = pd.to_numeric(all_data['amount'], errors='coerce')
            all_data.dropna(subset=['amount'], inplace=True)
            
            # Ensure 'date' is datetime
            all_data['date'] = pd.to_datetime(all_data['date'])

        except Exception as e:
            st.error(f"Error reading `Expenses` sheet from `{uploaded_file.name}`: {e}")
            st.info("The file might be corrupt, or the 'Expenses' sheet may be missing.")
            all_data = pd.DataFrame()

    # --- ALL OUR "VIBE" CHARTS (Now powered by 'Expenses' sheet) ---
    if not all_data.empty:
        
        # --- 1. CALCULATE METRICS (The *Correct* Way) ---
        
        # This is the fix: Only sum the 'amount' column!
        total_spent = all_data['amount'].sum() 
        
        # Multiply by -1 to show positive spending
        total_spent_positive = total_spent * -1 
        
        # Group by Category, sum *only* the 'amount'
        category_totals = all_data.groupby('Category')['amount'].sum() * -1
        
        top_category = category_totals.idxmax()
        top_category_value = category_totals.max()
        
        # Get date range for "avg per month"
        num_months = (all_data['date'].max() - all_data['date'].min()).days / 30.44
        num_months = max(1, num_months) # Avoid division by zero
        avg_per_month = total_spent_positive / num_months

        # --- 2. DISPLAY "HEADLINE NEWS" METRICS ---
        st.header("Headline News")
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.metric("Total Recorded Spend", f"${total_spent_positive:,.2f}")
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
            pie_data = category_totals.reset_index(name='Total')
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
            
            # Resample the raw data by month
            monthly_totals = all_data.set_index('date')['amount'].resample('M').sum() * -1
            heartbeat_data = pd.DataFrame(monthly_totals)
            heartbeat_data.index.name = 'Month'
            
            st.bar_chart(heartbeat_data, use_container_width=True, color="#00f2c3")
    else:
        if st.session_state.uploaded_master_file is not None:
            # This catches the case where the file was *bad*
            st.warning("Could not read any 'Expenses' data from the uploaded file.")
        else:
            # This is the normal "empty" state
            st.info("Your dashboard is empty.")