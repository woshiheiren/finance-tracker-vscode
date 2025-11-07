# 🚀 Woshi's Finance Tracker (Windows Guide) 🚀

Welcome! This is an application that turns your boring PDF bank statements into a powerful, interactive financial dashboard.

This guide will take you from a **blank Windows computer** to a **fully running app**. No coding knowledge needed!

---

## 🚀 How to Run This App (A Step-by-Step Guide for Windows)

Think of this as setting up a new, high-tech kitchen. You need to install the "oven" (Python), the "specialist tools" (Chocolatey), and then get the "ingredients" (the code).

### Phase 1: Install Your "Master Installer" (Chocolatey)

First, you need a tool called **Chocolatey**. It's the "Package Manager for coders" on Windows. It makes installing all the other tools *much* easier.

1.  Click your **Start Menu** and type `powershell`.
2.  Right-click on **"Windows PowerShell"** and choose **"Run as Administrator"**.
3.  You must first allow scripts to run. Copy and paste this command into PowerShell and press **Enter**:
    ```powershell
    Set-ExecutionPolicy AllSigned
    ```
    *(It might ask you to confirm, just type `Y` and press **Enter**).*
4.  Now, copy and paste this *entire* command into that same PowerShell window to install Chocolatey. It's a long one!
    ```powershell
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    ```
5.  After it finishes, **close the PowerShell window**.

### Phase 2: Install Your "Heavy Machinery"

Now we'll use our new "choco" command to install all the "heavy machinery" our app needs.

1.  **Re-open PowerShell** (as Administrator, just like before).
2.  First, we'll install Python, Ghostscript, and Tesseract (the "engine" for `ocrmypdf`):
    ```powershell
    choco install python3 ghostscript tesseract
    ```
    *(This will take a few minutes. Say 'Yes' to any prompts it gives you.)*
3.  **Critical Step (Poppler):** One of our "tools" (`poppler`) isn't in Chocolatey. We have to install it manually.
    * In your web browser, go to this page: **https://github.com/oschwartz10612/poppler-windows/releases**
    * Download the latest `.zip` file (e.g., `poppler-23.11.0.zip`).
    * Unzip this file somewhere permanent, like directly on your `C:\` drive (e.g., `C:\poppler-23.11.0`).
    * Now, we must **add this to your "PATH"** (so your computer knows where to find it).
    * Click your **Start Menu** and type `env`.
    * Click on **"Edit the system environment variables"**.
    * In the window that pops up, click the **"Environment Variables..."** button.
    * In the *bottom* box ("System variables"), find and double-click the variable named **`Path`**.
    * Click **"New"** and paste the *full path to the `bin` folder* from where you unzipped Poppler. For example:
        `C:\poppler-23.11.0\bin`
    * Click **"OK"** on all three windows to save and close.

### Phase 3: Get the Project Code

Now, let's copy the code from GitHub to your computer.

1.  **Close and Re-open** your PowerShell window (as Administrator) so it recognizes your new `Path`.
2.  We'll use `git` (the "magic camera"). Let's install it with choco:
    ```powershell
    choco install git
    ```
3.  **Close and Re-open PowerShell again** (as Administrator) so it recognizes `git`.
4.  Go to your Desktop:
    ```powershell
    cd Desktop
    ```
5.  "Clone" (copy) this project. **Replace `[YOUR_USERNAME]` with your actual GitHub username.**
    ```powershell
    git clone git@github.com:[YOUR_USERNAME]/finance-tracker-vscode.git
    ```
6.  Go into your new project folder:
    ```powershell
    cd finance-tracker-vscode
    ```

### Phase 4: Create the "Project Box" (Virtual Environment)

We need to create a clean "project box" for our app.

1.  Use Python to create the box:
    ```powershell
    python -m venv venv
    ```
2.  "Activate" the box. The command is different on Windows!
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
    *(You'll know it worked because your terminal prompt will now start with `(venv)`!)*

### Phase 5: Install the "App Ingredients"

Now that we're "in the box," we'll use our "shopping list" (`requirements.txt`) to install everything.

1.  Make sure you're still "in the box" (you see `(venv)`).
2.  Run this command:
    ```powershell
    pip install -r requirements.txt
    ```

### Phase 6: Add Your "Secret Key" (The AI Brain)

This part is identical to the Mac setup.

1.  Go to **https://aistudio.google.com/**.
2.  Sign in and get your free **API key**.
3.  In your project folder, create a **new folder** named `.streamlit`.
4.  Inside that `.streamlit` folder, create a **new file** named `secrets.toml`.
5.  Open `secrets.toml` (with Notepad or VS Code) and paste your key in this *exact* format:
    ```toml
    GEMINI_API_KEY = "PASTE_YOUR_LONG_SECRET_KEY_HERE"
    ```

### Phase 7: Run the App!

You are ready! All the hard work is done.

1.  Make sure you are in your project folder (`cd Desktop\finance-tracker-vscode`).
2.  Make sure your "project box" is active (`.\venv\Scripts\Activate.ps1`).
3.  Run this "bulletproof" command:
    ```powershell
    python -m streamlit run app.py
    ```

Your web browser will automatically open, and the app will be running!
