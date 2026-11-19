
import os
import requests
import streamlit as st

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

# --------------------------------
# 1. APP CONFIGURATION
# --------------------------------

st.set_page_config(
    page_title="CloudBox",
    page_icon="☁️",
    layout="wide"
)

load_dotenv(override=True)


def get_secret(name):
    """Read Streamlit Cloud secrets or local environment variables."""
    try:
        value = st.secrets[name]
        if value:
            return value
    except Exception:
        pass

    return os.getenv(name)


FIREBASE_API_KEY = get_secret("FIREBASE_API_KEY")
AZURE_STORAGE_CONNECTION_STRING = get_secret(
    "AZURE_STORAGE_CONNECTION_STRING"
)
AZURE_CONTAINER_NAME = get_secret("AZURE_CONTAINER_NAME")


# --------------------------------
# 2. SESSION STATE
# --------------------------------

if "user" not in st.session_state:
    st.session_state.user = None

if "id_token" not in st.session_state:
    st.session_state.id_token = None


# --------------------------------
# 3. FIREBASE AUTHENTICATION
# --------------------------------

def firebase_auth(endpoint, email, password):
    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:{endpoint}?key={FIREBASE_API_KEY}"
    )

    response = requests.post(
        url,
        json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        },
        timeout=20
    )

    data = response.json()

    if response.status_code != 200:
        message = data.get("error", {}).get(
            "message", "Authentication failed"
        )
        raise Exception(message)

    return data


def verify_firebase_token(id_token):
    """Verify the Firebase ID token and obtain the authenticated UID."""
    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:lookup?key={FIREBASE_API_KEY}"
    )

    response = requests.post(
        url,
        json={"idToken": id_token},
        timeout=20
    )

    if response.status_code != 200:
        return None

    users = response.json().get("users", [])

    if not users:
        return None

    return users[0].get("localId")


# --------------------------------
# 4. AZURE STORAGE CONNECTION
# --------------------------------

def get_blob_container():
    if not AZURE_STORAGE_CONNECTION_STRING:
        raise ValueError("Azure connection string is missing.")

    if not AZURE_CONTAINER_NAME:
        raise ValueError("Azure container name is missing.")

    blob_service = BlobServiceClient.from_connection_string(
        AZURE_STORAGE_CONNECTION_STRING
    )

    return blob_service.get_container_client(
        AZURE_CONTAINER_NAME
    )


# --------------------------------
# 5. CUSTOM STYLING
# --------------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #101827, #172554);
    color: white;
}

.main-title {
    font-size: 42px;
    font-weight: 800;
    color: #ffffff;
}

.subtitle {
    color: #b8c7e0;
    font-size: 16px;
}

div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

[data-testid="stSidebar"] {
    background-color: #111c32;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------
# 6. HEADER
# --------------------------------

st.markdown(
    '<div class="main-title">☁️ CloudBox</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Your personal cloud file storage and sharing platform'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# --------------------------------
# 7. CHECK CONFIGURATION
# --------------------------------

if not FIREBASE_API_KEY:
    st.error("Firebase API key is missing.")
    st.stop()

if not AZURE_STORAGE_CONNECTION_STRING:
    st.error("Azure storage connection string is missing.")
    st.stop()

if not AZURE_CONTAINER_NAME:
    st.error("Azure container name is missing.")
    st.stop()


# --------------------------------
# 8. LOGIN AND REGISTRATION
# --------------------------------

if not st.session_state.id_token:

    st.subheader("Welcome to CloudBox")

    login_tab, signup_tab = st.tabs(
        ["Login", "Create Account"]
    )

    with login_tab:

        st.write("Sign in to access your cloud files.")

        login_email = st.text_input(
            "Email address",
            key="login_email"
        )

        login_password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login", use_container_width=True):

            if not login_email or not login_password:
                st.warning("Enter your email and password.")

            else:
                try:
                    with st.spinner("Signing in..."):

                        result = firebase_auth(
                            "signInWithPassword",
                            login_email,
                            login_password
                        )

                        st.session_state.id_token = result["idToken"]
                        st.session_state.user = {
                            "email": result["email"]
                        }

                    st.success("Login successful!")
                    st.rerun()

                except Exception as error:
                    st.error(f"Login failed: {error}")

    with signup_tab:

        st.write("Create your free CloudBox account.")

        signup_email = st.text_input(
            "Email address",
            key="signup_email"
        )

        signup_password = st.text_input(
            "Create password",
            type="password",
            key="signup_password"
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
            key="confirm_password"
        )

        if st.button(
            "Create Account",
            use_container_width=True
        ):

            if not signup_email or not signup_password:
                st.warning("Complete all fields.")

            elif signup_password != confirm_password:
                st.error("Passwords do not match.")

            elif len(signup_password) < 6:
                st.warning(
                    "Password must contain at least 6 characters."
                )

            else:
                try:
                    with st.spinner("Creating account..."):

                        result = firebase_auth(
                            "signUp",
                            signup_email,
                            signup_password
                        )

                        st.session_state.id_token = result["idToken"]
                        st.session_state.user = {
                            "email": result["email"]
                        }

                    st.success("Account created successfully!")
                    st.rerun()

                except Exception as error:
                    st.error(f"Registration failed: {error}")

    st.stop()


# --------------------------------
# 9. VERIFY USER SESSION
# --------------------------------

try:
    verified_uid = verify_firebase_token(
        st.session_state.id_token
    )

    if not verified_uid:
        st.session_state.user = None
        st.session_state.id_token = None
        st.error("Your session has expired. Please log in again.")
        st.rerun()

except requests.RequestException:
    st.error("Unable to verify your session. Check your connection.")
    st.stop()


# --------------------------------
# 10. USER DASHBOARD
# --------------------------------

user_email = st.session_state.user["email"]

with st.sidebar:

    st.title("☁️ CloudBox")

    st.write("### My Account")
    st.write(user_email)

    st.divider()

    st.caption("Cloud Storage")
    st.write("Azure Blob Storage")

    st.caption("Authentication")
    st.write("Firebase Authentication")

    st.divider()

    if st.button("Logout", use_container_width=True):

        st.session_state.user = None
        st.session_state.id_token = None
        st.rerun()


st.subheader("My Dashboard")

st.write(f"Welcome back, **{user_email}**!")

# Each user's files are stored under their Firebase UID.
user_prefix = f"{verified_uid}/"


# --------------------------------
# 11. CONNECT TO AZURE
# --------------------------------

try:
    container_client = get_blob_container()

except Exception as error:
    st.error(f"Azure connection failed: {error}")
    st.stop()


# --------------------------------
# 12. FILE UPLOAD
# --------------------------------

st.subheader("📤 Upload Files")

uploaded_file = st.file_uploader(
    "Choose a file to upload",
    help="Select a file from your device."
)

if uploaded_file is not None:

    st.write(f"Selected file: **{uploaded_file.name}**")

    if st.button("Upload to CloudBox"):

        try:
            blob_name = user_prefix + uploaded_file.name

            with st.spinner("Uploading file to Azure..."):

                container_client.upload_blob(
                    name=blob_name,
                    data=uploaded_file.getvalue(),
                    overwrite=True
                )

            st.success("File uploaded successfully!")
            st.rerun()

        except Exception as error:
            st.error(f"Upload failed: {error}")


st.divider()


# --------------------------------
# 13. LIST USER FILES
# --------------------------------

st.subheader("📁 My Cloud Files")

try:

    user_blobs = list(
        container_client.list_blobs(
            name_starts_with=user_prefix
        )
    )

    if not user_blobs:

        st.info("No files uploaded yet. Upload your first file!")

    else:

        st.write(f"Total files: **{len(user_blobs)}**")

        for blob in user_blobs:

            file_name = blob.name[len(user_prefix):]

            with st.container(border=True):

                col1, col2, col3 = st.columns(
                    [3, 1, 1]
                )

                with col1:
                    st.write(f"📄 **{file_name}**")
                    st.caption(
                        f"Size: {blob.size / 1024:.2f} KB"
                    )

                with col2:

                    try:
                        file_data = (
                            container_client
                            .get_blob_client(blob.name)
                            .download_blob()
                            .readall()
                        )

                        st.download_button(
                            "Download",
                            data=file_data,
                            file_name=file_name,
                            key=f"download_{blob.name}",
                            use_container_width=True
                        )

                    except Exception as error:
                        st.error("Download unavailable.")

                with col3:

                    if st.button(
                        "Delete",
                        key=f"delete_{blob.name}",
                        use_container_width=True
                    ):

                        try:
                            container_client.delete_blob(
                                blob.name
                            )

                            st.success(
                                f"{file_name} deleted."
                            )

                            st.rerun()

                        except ResourceNotFoundError:
                            st.warning("File already deleted.")

                        except Exception as error:
                            st.error(
                                f"Delete failed: {error}"
                            )

except Exception as error:
    st.error(f"Unable to list files: {error}")


# --------------------------------
# 14. FOOTER
# --------------------------------

st.divider()

st.caption(
    "CloudBox | Cloud File Storage & Sharing App | "
    "Powered by Firebase and Microsoft Azure"
)
