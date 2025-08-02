import hashlib
import secrets
from typing import Optional
from database.database import get_session
from database.models import User

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        salt, hash_value = password_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == hash_value
    except ValueError:
        return False

def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password"""
    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()
        
        if user and verify_password(password, user.password_hash):
            return user
        return None
    finally:
        session.close()

def get_current_user(user_id: int) -> Optional[User]:
    """Get user by ID"""
    session = get_session()
    try:
        user = session.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        return user
    finally:
        session.close()

def check_permission(user: User, required_role: str) -> bool:
    """Check if user has required role/permission"""
    role_hierarchy = {
        'viewer': 1,
        'trader': 2,
        'admin': 3
    }
    
    user_level = role_hierarchy.get(user.role, 0)
    required_level = role_hierarchy.get(required_role, 99)
    
    return user_level >= required_level

def create_user(username: str, email: str, password: str, role: str = 'trader') -> User:
    """Create a new user"""
    session = get_session()
    try:
        # Check if username or email already exists
        existing = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            raise ValueError("Username or email already exists")
        
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True
        )
        
        session.add(user)
        session.commit()
        return user
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def update_user_role(user_id: int, new_role: str) -> bool:
    """Update user role"""
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = new_role
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()

def deactivate_user(user_id: int) -> bool:
    """Deactivate a user"""
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = False
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()
