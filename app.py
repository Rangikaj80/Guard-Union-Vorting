import streamlit as st
import pandas as pd
import qrcode
import os
import time
from PIL import Image
import base64
import sqlite3
from datetime import datetime
import cv2
import numpy as np
import io

# Set page configuration
st.set_page_config(
    page_title="Railway Guard Union",
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create directory structure
os.makedirs("qr_codes", exist_ok=True)
os.makedirs("candidate_photos", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Database functions
def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect('union_voting.db')
    c = conn.cursor()
    
    # Members table
    c.execute('''CREATE TABLE IF NOT EXISTS members
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                department TEXT,
                registered_date TEXT,
                qr_code_path TEXT,
                is_approved INTEGER DEFAULT 0,
                has_voted INTEGER DEFAULT 0)''')
    
    # Candidates table
    c.execute('''CREATE TABLE IF NOT EXISTS candidates
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                position TEXT NOT NULL,
                bio TEXT,
                photo_path TEXT)''')
    
    # Votes table
    c.execute('''CREATE TABLE IF NOT EXISTS votes
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id INTEGER NOT NULL,
                position TEXT NOT NULL,
                candidate_id INTEGER NOT NULL,
                vote_time TEXT)''')
    
    # Admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL)''')
    
    # Check if default admin exists
    c.execute("SELECT * FROM admins WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admins (username, password) VALUES ('admin', 'railway@123')")
    
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# Helper functions
def get_member_data(member):
    """Safely extract member data regardless of database schema"""
    if member is None:
        return None
    
    # Create a dictionary with default values
    member_dict = {
        'id': None, 
        'name': None, 
        'employee_id': None, 
        'department': None, 
        'registered_date': None,
        'qr_code_path': None, 
        'is_approved': 0, 
        'has_voted': 0
    }
    
    # Fill the dictionary with actual values
    for i, column in enumerate(member):
        if i == 0:
            member_dict['id'] = column
        elif i == 1:
            member_dict['name'] = column
        elif i == 2:
            member_dict['employee_id'] = column
        elif i == 3:
            member_dict['department'] = column
        elif i == 4:
            member_dict['registered_date'] = column
        elif i == 5:
            member_dict['qr_code_path'] = column
        elif i == 6:
            member_dict['is_approved'] = column
        elif i == 7:
            member_dict['has_voted'] = column
    
    return member_dict

def generate_qr_code(data, employee_id):
    """Generate a QR code for a member"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    qr_code_path = f"qr_codes/{employee_id}.png"
    img.save(qr_code_path)
    return qr_code_path

def get_binary_file_downloader_html(file_path, file_label='File'):
    """Create an HTML download link for a file"""
    with open(file_path, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(file_path)}">Download {file_label}</a>'
    return href

def decode_qr_code(uploaded_file):
    """Decode a QR code from an uploaded image"""
    try:
        # Read the image file
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # Check if image was loaded properly
        if img is None:
            st.error("Failed to load image. Please try another image.")
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Try with QRCodeDetector
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(gray)
        
        if data:
            return data
        
        # If no QR code found, try with a different preprocessing
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        data, bbox, _ = detector.detectAndDecode(binary)
        
        if data:
            return data
        
        # Try to decode with pyzbar if available
        try:
            import pyzbar.pyzbar as pyzbar
            # Rewind the file
            uploaded_file.seek(0)
            pil_image = Image.open(uploaded_file)
            decoded_objects = pyzbar.decode(pil_image)
            if decoded_objects:
                return decoded_objects[0].data.decode('utf-8')
        except ImportError:
            pass  # pyzbar not available
        
        return None
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

def authenticate_admin(username, password):
    """Authenticate an admin user"""
    conn = sqlite3.connect('union_voting.db')
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
    admin = c.fetchone()
    conn.close()
    return admin is not None

# Page functions
def home_page():
    """Display the home page"""
    st.title("Railway Guard Union Voting System")
    st.write("Welcome to the Railway Guard Union Voting System. Use the sidebar to navigate.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("For Members")
        st.write("• Register as a member")
        st.write("• Retrieve your QR code if needed")
        st.write("• View candidates and their profiles")
        st.write("• Vote for your preferred candidates")
        
    with col2:
        st.subheader("For Administrators")
        st.write("• Approve member registrations")
        st.write("• Manage candidates")
        st.write("• View election results")
        
    st.info("Note: You need to register and get admin approval before you can vote.")

def member_registration():
    """Handle member registration"""
    st.title("Railway Guard Union - Member Registration")
    
    with st.form("registration_form"):
        name = st.text_input("Full Name")
        employee_id = st.text_input("Employee ID")
        department = st.selectbox("Department", ["Colombo", "Kandy", "Galle", "Jaffna", "Anuradhapura", "Other"])
        submit_button = st.form_submit_button("Register")
        
        if submit_button:
            if name and employee_id:
                conn = sqlite3.connect('union_voting.db')
                c = conn.cursor()
                
                # Check if employee ID already exists
                c.execute("SELECT * FROM members WHERE employee_id=?", (employee_id,))
                if c.fetchone():
                    st.error("This employee ID is already registered.")
                else:
                    # Generate QR code
                    qr_data = f"RailwayGuardUnion:{employee_id}:{name}"
                    qr_code_path = generate_qr_code(qr_data, employee_id)
                    
                    # Insert into database
                    registered_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        c.execute("INSERT INTO members (name, employee_id, department, registered_date, qr_code_path) VALUES (?, ?, ?, ?, ?)",
                                  (name, employee_id, department, registered_date, qr_code_path))
                        conn.commit()
                        
                        # Show success message and QR code with download option
                        st.success("Registration successful! Your application is pending admin approval.")
                        st.image(qr_code_path, caption="Your Member QR Code", width=200)
                        st.markdown(get_binary_file_downloader_html(qr_code_path, "QR Code"), unsafe_allow_html=True)
                        st.write("Download this QR code and present it when voting.")
                    except Exception as e:
                        st.error(f"Error during registration: {e}")
                        if os.path.exists(qr_code_path):
                            os.remove(qr_code_path)
            else:
                st.warning("Please fill all required fields.")
                
            conn.close()

def find_qr_code():
    """Find and download a member's QR code"""
    st.title("Find Your QR Code")
    
    col1, col2 = st.columns(2)
    
    with col1:
        search_type = st.radio("Search by:", ["Employee ID", "Name"])
    
    with col2:
        if search_type == "Employee ID":
            search_term = st.text_input("Enter your Employee ID")
            search_field = "employee_id"
        else:
            search_term = st.text_input("Enter your Name")
            search_field = "name"
    
    if st.button("Find My QR Code") and search_term:
        conn = sqlite3.connect('union_voting.db')
        c = conn.cursor()
        
        # Search for member
        c.execute(f"SELECT * FROM members WHERE {search_field}=?", (search_term,))
        member_data = c.fetchone()
        
        if member_data:
            member = get_member_data(member_data)
            
            st.success(f"Found record for {member['name']} ({member['employee_id']})")
            
            if member['qr_code_path'] and os.path.exists(member['qr_code_path']):
                st.image(member['qr_code_path'], caption="Your Member QR Code", width=200)
                st.markdown(get_binary_file_downloader_html(member['qr_code_path'], "QR Code"), unsafe_allow_html=True)
                st.write("Download this QR code and present it when voting.")
                
                # Display member status
                if member['is_approved']:
                    status = "Approved" if not member['has_voted'] else "Voted"
                else:
                    status = "Pending Approval"
                
                st.info(f"Member Status: {status}")
            else:
                st.error("QR code not found. Please contact an administrator.")
        else:
            st.error(f"No member found with the provided {search_type.lower()}.")
        
        conn.close()

def view_candidates():
    """Display all candidates and their information"""
    st.title("View Candidates")
    
    conn = sqlite3.connect('union_voting.db')
    c = conn.cursor()
    
    # Get all positions
    c.execute("SELECT DISTINCT position FROM candidates")
    positions = [row[0] for row in c.fetchall()]
    
    if not positions:
        st.info("No candidates have been registered yet.")
    else:
        for position in positions:
            st.subheader(position)
            
            # Get candidates for this position
            c.execute("SELECT * FROM candidates WHERE position=?", (position,))
            candidates = c.fetchall()
            
            if not candidates:
                st.write("No candidates for this position")
                continue
            
            # Display candidates
            cols = st.columns(min(3, len(candidates)))
            for i, candidate in enumerate(candidates):
                c_id, name, employee_id, position, bio, photo_path = candidate
                with cols[i % len(cols)]:
                    st.write(f"**{name}**")
                    if photo_path and os.path.exists(photo_path):
                        st.image(photo_path, width=150)
                    else:
                        st.write("*No photo available*")
                    st.write(f"Employee ID: {employee_id}")
                    if bio:
                        st.write(f"{bio}")
                    st.write("---")
    
    conn.close()

def voting_page():
    """Handle the voting process"""
    st.title("Railway Guard Union - Voting")
    
    # QR Code upload section
    uploaded_file = st.file_uploader("Upload your member QR code", type=["png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Decode QR code
        qr_data = decode_qr_code(uploaded_file)
        
        if qr_data:
            try:
                # Parse QR code data (format: RailwayGuardUnion:employee_id:name)
                parts = qr_data.split(":")
                if len(parts) == 3 and parts[0] == "RailwayGuardUnion":
                    employee_id = parts[1]
                    name_from_qr = parts[2]
                    
                    conn = sqlite3.connect('union_voting.db')
                    c = conn.cursor()
                    
                    # Check member status - verify identity
                    c.execute("SELECT * FROM members WHERE employee_id=?", (employee_id,))
                    member_data = c.fetchone()
                    
                    if member_data:
                        member = get_member_data(member_data)
                        
                        # Display verification message
                        st.success(f"Identity Verified: {member['name']} ({member['employee_id']})")
                        
                        # Check if already voted
                        if member['has_voted'] == 1:
                            st.error("You have already voted. Each member can vote only once.")
                            conn.close()
                            return
                        
                        # Check if approved
                        if member['is_approved'] != 1:
                            st.warning("Your registration is pending admin approval. You can view candidates but cannot vote until approved.")
                            
                            # Show candidates in read-only mode
                            st.subheader("Available Candidates")
                            c.execute("SELECT DISTINCT position FROM candidates")
                            positions = [row[0] for row in c.fetchall()]
                            
                            for position in positions:
                                c.execute("SELECT * FROM candidates WHERE position=?", (position,))
                                pos_candidates = c.fetchall()
                                
                                if pos_candidates:
                                    st.write(f"**{position}**")
                                    cols = st.columns(min(3, len(pos_candidates)))
                                    for i, candidate in enumerate(pos_candidates):
                                        c_id, name, emp_id, pos, bio, photo_path = candidate
                                        with cols[i % len(cols)]:
                                            st.write(f"{name} ({emp_id})")
                            
                            conn.close()
                            return
                        
                        # Member is approved and hasn't voted yet - show voting form
                        st.info("You are approved to vote. Please select your candidates below.")
                        
                        # Get all positions
                        positions = [
                            "President",
                            "Vice President 1",
                            "Vice President 2",
                            "Secretary",
                            "Assistant Secretary",
                            "Treasurer",
                            "Assistant Treasurer",
                            "Committee Member 1",
                            "Committee Member 2",
                            "Committee Member 3",
                            "Committee Member 4",
                            "Committee Member 5",
                            "Committee Member 6",
                            "Committee Member 7",
                            "Committee Member 8",
                            "Committee Member 9"
                        ]
                        
                        # Get candidates for each position
                        c.execute("SELECT * FROM candidates")
                        candidates = c.fetchall()
                        
                        # Voting form
                        with st.form("voting_form"):
                            votes = {}
                            for position in positions:
                                pos_candidates = [c for c in candidates if c[3] == position]
                                if pos_candidates:
                                    candidate_names = [f"{c[1]} ({c[2]})" for c in pos_candidates]
                                    selected = st.radio(
                                        f"Select {position}",
                                        candidate_names,
                                        key=position
                                    )
                                    selected_id = pos_candidates[candidate_names.index(selected)][0]
                                    votes[position] = selected_id
                                else:
                                    st.write(f"No candidates for {position}")
                            
                            submit_vote = st.form_submit_button("Submit Vote")
                            
                            if submit_vote:
                                # Only mark as voted after successful submission
                                vote_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                try:
                                    # Insert all votes
                                    for position, candidate_id in votes.items():
                                        c.execute("INSERT INTO votes (voter_id, position, candidate_id, vote_time) VALUES (?, ?, ?, ?)",
                                                (member['id'], position, candidate_id, vote_time))
                                    
                                    # Mark member as voted ONLY after successful vote
                                    c.execute("UPDATE members SET has_voted=1 WHERE id=?", (member['id'],))
                                    conn.commit()
                                    st.success("Thank you for voting! Your vote has been recorded.")
                                    time.sleep(2)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error recording vote: {e}")
                                    conn.rollback()
                    else:
                        st.error("Member not found. Please register first.")
                    
                    conn.close()
                else:
                    st.error("Invalid QR code format. Please upload your member QR code.")
            except Exception as e:
                st.error(f"Error processing QR code: {e}")
                st.error("Please try uploading a clearer image of your QR code.")
        else:
            st.error("Could not read QR code. Please upload a clear image of your QR code.")

def admin_approval():
    """Handle admin member approval and management"""
    st.title("Admin - Member Approval")
    
    # Admin login
    if 'admin_logged_in' not in st.session_state:
        with st.form("admin_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")
            
            if login_button:
                if authenticate_admin(username, password):
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        return
    
    st.write(f"Logged in as: **Admin**")
    
    # Add option to verify database state
    if st.checkbox("Debug Database"):
        # Debug section to check database state
        conn = sqlite3.connect('union_voting.db')
        c = conn.cursor()
        c.execute("SELECT id, name, employee_id, is_approved, has_voted FROM members")
        members = c.fetchall()
        if members:
            st.write("Current Database State:")
            for m in members:
                st.write(f"ID: {m[0]}, Name: {m[1]}, Employee ID: {m[2]}, Approved: {m[3]}, Has Voted: {m[4]}")
        else:
            st.write("No members in database")
        conn.close()
    
    # Show pending approvals
    conn = sqlite3.connect('union_voting.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM members WHERE is_approved=0")
    pending_members = c.fetchall()
    
    if not pending_members:
        st.info("No pending approvals")
    else:
        st.subheader("Pending Approvals")
        for member_data in pending_members:
            member = get_member_data(member_data)
            
            with st.expander(f"{member['name']} - {member['employee_id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Department:** {member['department']}")
                    st.write(f"**Registered on:** {member['registered_date']}")
                    if member['qr_code_path'] and os.path.exists(member['qr_code_path']):
                        st.image(member['qr_code_path'], width=150)
                    else:
                        st.write("QR code not found")
                with col2:
                    if st.button(f"Approve {member['name']}", key=f"approve_{member['id']}"):
                        try:
                            # Only update is_approved field, not has_voted
                            c.execute("UPDATE members SET is_approved=1 WHERE id=?", (member['id'],))
                            conn.commit()
                            st.success(f"{member['name']} approved!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error approving member: {e}")
    
    # View all approved members
    st.subheader("Approved Members")
    c.execute("SELECT * FROM members WHERE is_approved=1")
    approved_members = c.fetchall()
    
    if not approved_members:
        st.info("No approved members yet")
    else:
        member_data_list = []
        for member_data in approved_members:
            member = get_member_data(member_data)
            member_data_list.append({
                "Name": member['name'],
                "Employee ID": member['employee_id'],
                "Department": member['department'],
                "Voted": "Yes" if member['has_voted'] else "No"
            })
        
        member_df = pd.DataFrame(member_data_list)
        st.dataframe(member_df)
        
        # Add option to reset voted status (for testing)
        if st.checkbox("Show Admin Tools"):
            if st.button("Reset All Voting Status"):
                try:
                    c.execute("UPDATE members SET has_voted=0")
                    conn.commit()
                    st.success("All members' voting status reset!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error resetting voting status: {e}")
                
            # Add complete database reset option
            st.write("---")
            st.write("⚠️ **Danger Zone** ⚠️")
            if st.button("Reset Entire Database", help="This will delete all data and reset the database"):
                try:
                    # Close current connection
                    conn.close()
                    # Delete database file
                    if os.path.exists("union_voting.db"):
                        os.remove("union_voting.db")
                    # Reinitialize the database
                    init_db()
                    st.success("Database completely reset!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error resetting database: {e}")
    
    conn.close()

def candidate_management():
    """Handle candidate addition and management"""
    st.title("Admin - Candidate Management")
    
    if 'admin_logged_in' not in st.session_state:
        st.warning("Please login as admin first")
        return
    
    tab1, tab2 = st.tabs(["Add Candidate", "View Candidates"])
    
    with tab1:
        with st.form("add_candidate"):
            name = st.text_input("Candidate Name")
            employee_id = st.text_input("Employee ID")
            position = st.selectbox("Position", [
                "President",
                "Vice President 1",
                "Vice President 2",
                "Secretary",
                "Assistant Secretary",
                "Treasurer",
                "Assistant Treasurer",
                "Committee Member 1",
                "Committee Member 2",
                "Committee Member 3",
                "Committee Member 4",
                "Committee Member 5",
                "Committee Member 6",
                "Committee Member 7",
                "Committee Member 8",
                "Committee Member 9"
            ])
            bio = st.text_area("Short Biography")
            photo = st.file_uploader("Candidate Photo", type=["png", "jpg", "jpeg"])
            
            submit = st.form_submit_button("Add Candidate")
            
            if submit:
                if name and employee_id and position:
                    conn = sqlite3.connect('union_voting.db')
                    c = conn.cursor()
                    
                    # Save photo if uploaded
                    photo_path = None
                    if photo:
                        os.makedirs("candidate_photos", exist_ok=True)
                        photo_path = f"candidate_photos/{employee_id}.{photo.name.split('.')[-1]}"
                        with open(photo_path, "wb") as f:
                            f.write(photo.getbuffer())
                    
                    try:
                        c.execute("INSERT INTO candidates (name, employee_id, position, bio, photo_path) VALUES (?, ?, ?, ?, ?)",
                                  (name, employee_id, position, bio, photo_path))
                        conn.commit()
                        st.success("Candidate added successfully!")
                    except sqlite3.IntegrityError:
                        st.error("A candidate with this employee ID already exists")
                    except Exception as e:
                        st.error(f"Error adding candidate: {e}")
                        if photo_path and os.path.exists(photo_path):
                            os.remove(photo_path)
                    
                    conn.close()
                else:
                    st.warning("Please fill all required fields")
    
    with tab2:
        conn = sqlite3.connect('union_voting.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM candidates")
        candidates = c.fetchall()
        
        if not candidates:
            st.info("No candidates registered yet")
        else:
            for candidate in candidates:
                c_id, name, employee_id, position, bio, photo_path = candidate
                
                with st.expander(f"{position}: {name}"):
                    cols = st.columns([1, 3])
                    with cols[0]:
                        if photo_path and os.path.exists(photo_path):
                            st.image(photo_path, width=150)
                        else:
                            st.write("No photo")
                    with cols[1]:
                        st.write(f"**Employee ID:** {employee_id}")
                        st.write(f"**Bio:** {bio}")
                    
                    if st.button(f"Remove {name}", key=f"remove_{c_id}"):
                        try:
                            c.execute("DELETE FROM candidates WHERE id=?", (c_id,))
                            conn.commit()
                            if photo_path and os.path.exists(photo_path):
                                os.remove(photo_path)
                            st.success("Candidate removed")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error removing candidate: {e}")
        
        conn.close()

def view_results():
    """Display voting results"""
    st.title("Election Results")
    
    if 'admin_logged_in' not in st.session_state:
        st.warning("Please login as admin to view detailed results")
        
        # Show simplified results for non-admins
        conn = sqlite3.connect('union_voting.db')
        c = conn.cursor()
        
        # Get total votes
        c.execute("SELECT COUNT(DISTINCT voter_id) FROM votes")
        total_voters = c.fetchone()[0]
        st.write(f"**Total Votes Cast:** {total_voters}")
        
        # Show winner for each position
        c.execute("SELECT DISTINCT position FROM candidates")
        positions = [row[0] for row in c.fetchall()]
        
        st.subheader("Election Winners")
        for position in positions:
            c.execute("""
                SELECT c.name, COUNT(*) as vote_count
                FROM votes v
                JOIN candidates c ON v.candidate_id = c.id
                WHERE v.position = ?
                GROUP BY v.candidate_id
                ORDER BY vote_count DESC
                LIMIT 1
            """, (position,))
            result = c.fetchone()
            if result:
                winner, votes = result
                st.write(f"**{position}:** {winner} ({votes} votes)")
        
        conn.close()
        return
    
    conn = sqlite3.connect('union_voting.db')
    c = conn.cursor()
    
    # Get voting statistics
    c.execute("SELECT COUNT(*) FROM members WHERE is_approved=1")
    total_members = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM members WHERE has_voted=1")
    total_voted = c.fetchone()[0]
    
    if total_members > 0:
        voting_percentage = (total_voted / total_members) * 100
    else:
        voting_percentage = 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Eligible Voters", total_members)
    col2.metric("Total Votes Cast", total_voted)
    col3.metric("Voting Percentage", f"{voting_percentage:.2f}%")
    
    # Get all positions
    c.execute("SELECT DISTINCT position FROM candidates")
    positions = [row[0] for row in c.fetchall()]
    
    for position in positions:
        st.subheader(position)
        
        # Get candidates for this position
        c.execute("SELECT id, name FROM candidates WHERE position=?", (position,))
        candidates = c.fetchall()
        
        if not candidates:
            st.write("No candidates for this position")
            continue
        
        # Get votes for each candidate
        votes_data = []
        for candidate in candidates:
            c_id, name = candidate
            c.execute("SELECT COUNT(*) FROM votes WHERE position=? AND candidate_id=?", (position, c_id))
            vote_count = c.fetchone()[0]
            votes_data.append({"Candidate": name, "Votes": vote_count})
        
        # Display as table and bar chart
        df = pd.DataFrame(votes_data).sort_values("Votes", ascending=False)
        st.table(df)
        if not df.empty:  # Check if DataFrame is not empty before creating chart
            st.bar_chart(df.set_index("Candidate"))
    
    conn.close()

# Main app function
def main():
    """Main function to control the multi-page application"""
    st.sidebar.title("Railway Guard Union")
    st.sidebar.image("https://www.railway.gov.lk/web/images/logo.png", width=100)
    
    # Navigation
    app_mode = st.sidebar.radio("Navigation", [
        "Home",
        "Member Registration",
        "Find My QR Code",
        "View Candidates",
        "Voting",
        "Admin Login",
        "Candidate Management",
        "View Results"
    ])
    
    # Display the selected page
    if app_mode == "Home":
        home_page()
    elif app_mode == "Member Registration":
        member_registration()
    elif app_mode == "Find My QR Code":
        find_qr_code()
    elif app_mode == "View Candidates":
        view_candidates()
    elif app_mode == "Voting":
        voting_page()
    elif app_mode == "Admin Login":
        admin_approval()
    elif app_mode == "Candidate Management":
        candidate_management()
    elif app_mode == "View Results":
        view_results()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info("© 2023 Railway Guard Union")

if __name__ == "__main__":
    main()