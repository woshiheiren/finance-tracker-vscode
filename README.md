# 💰 Vibe Coder's AI Finance Tracker 💰

**Looking for the Windows guide? [Click here!](README-Windows.md)**

Welcome! This is a "vibe-coded" application that turns your boring PDF bank statements into a powerful, interactive financial dashboard. It uses AI to automatically categorize your spending, lets you edit everything, and saves it all to a master spreadsheet.

This guide will take you from a **blank Mac computer** to a **fully running app**. No coding knowledge needed!



---

## ✨ Features

* **PDF Processing:** Upload one (or many!) PDF bank statements.
* **AI-Powered Categorization:** A Google AI (Gemini) automatically reads your transaction descriptions (like "Starbucks") and guesses the category (like "Food").
* **Fully Editable Preview:** A "mini-Excel" sheet lets you fix any AI mistakes, add/delete rows, and change categories from a dropdown.
* **Smart Saving:** Automatically saves your clean data to a `master_spreadsheet.xlsx` file on your computer, with a separate tab for each month (e.g., "July 2025").
* **Live Dashboard:** A beautiful, multi-chart dashboard (with a "Gradient Glow" vibe!) that reads your master spreadsheet and shows you:
    * **Headline News:** Your total spending, top category, and monthly average.
    * **The Spending Pie:** A donut chart of your spending by category.
    * **The Financial Heartbeat:** A bar chart of your spending over time.
* **Custom "Vibe":** A custom-coded dark-mode theme with a "Space Mono" font.

---

## 🚀 How to Run This App (A Step-by-Step Guide for macOS)

Think of this as setting up a new, high-tech kitchen. You need to install the "oven" (Python), the "specialist tools" (Homebrew), and then get the "ingredients" (the code).

### Phase 1: Install Your "Master Installer" (Homebrew)

First, you need a tool called **Homebrew**. It's the "App Store for coders" on a Mac. It makes installing all the other tools a breeze.

1.  Open your **Terminal** (find it in Applications > Utilities > Terminal).
2.  Copy and paste this *entire* command into your Terminal and press **Enter**. It will ask for your Mac's password (you won't see the letters as you type, that's normal).

    ```bash
    /bin/bash -c "$(curl -fsSL [https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh](https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh))"
    ```

### Phase 2: Install Your "Heavy Machinery"

Now we'll use Homebrew (`brew`) to install our "oven" (a stable version of Python) and all the "power outlets" our app needs to read PDFs and data.

1.  In that same **Terminal**, run this single command:

    ```bash
    brew install python@3.12 apache-arrow poppler ocrmypdf pkg-config gcc@11
    ```

### Phase 3: Get the Project Code (From This Gallery!)

Now, let's copy all the code from this GitHub "gallery" to a folder on your computer.

1.  We'll use a program called `git` (the "magic camera" for code). Homebrew should have installed it, but if not, run `brew install git`.
2.  Go to your Desktop (or wherever you want to save this project):
    ```bash
    cd Desktop
    ```
3.  "Clone" (copy) this project:
    ```bash
    git clone git@github.com:[YOUR_USERNAME]/finance-tracker-vscode.git
    ```
4.  Go into your new project folder:
    ```bash
    cd finance-tracker-vscode
    ```

### Phase 4: Create the "Project Box" (Virtual Environment)

We need to create a clean, separate "project box" so our app's "ingredients" don't get mixed up with your Mac's.

1.  Use our stable Python 3.12 to create the box:
    ```bash
    python3.12 -m venv venv
    ```
2.  "Activate" the box. You **must** do this every time you run the app.
    ```bash
    source venv/bin/activate
    ```
    *(You'll know it worked because your terminal prompt will now start with `(venv)`!)*

### Phase 5: Install the "App Ingredients"

Now that we're "in the box," we'll use our "shopping list" (`requirements.txt`) to install all the app's ingredients at once.

1.  Make sure you're still "in the box" (you see `(venv)`).
2.  Run this command:
    ```bash
    pip install -r requirements.txt
    ```

### Phase 6: Add Your "Secret Key" (The AI Brain)

This is the only "manual" part. You need a free "key card" from Google to use the AI.

1.  Go to **https://aistudio.google.com/** in your web browser.
2.  Sign in with your Google account.
3.  Click **"Get API key"** and "Create API key in new project."
4.  Copy the long, secret key it gives you (e.g., `AIzaSy...`).
5.  Back in your project folder (in VS Code or Finder), create a **new folder** named `.streamlit`.
6.  Inside that `.streamlit` folder, create a **new file** named `secrets.toml`.
7.  Open `secrets.toml` and paste your key in this *exact* format:
    ```toml
    GEMINI_API_KEY = "PASTE_YOUR_LONG_SECRET_KEY_HERE"
    ```

### Phase 7: Run the App!

You are ready. You've done all the setup.

1.  Make sure you are in your project folder (`cd Desktop/finance-tracker-vscode`).
2.  Make sure your "project box" is active (`source venv/bin/activate`).
3.  Run this "bulletproof" command:
    ```bash
    python -m streamlit run app.py
    ```

Your web browser will automatically open, and your **Vibe Coder Finance Tracker** will be running live!

---

## 💻 Technologies Used

* **Python** (The "Language")
* **Streamlit** (The "App Builder")
* **Pandas** (The "Spreadsheet Expert")
* **Google Gemini AI** (The "AI Brain")
* **Monopoly-Core** (The "PDF Reader")
* **Altair** (The "Chart Maker")
* **OpenPyXL / XlsxWriter** (The "Excel Writers")