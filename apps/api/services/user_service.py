"""
User Service 
Business logic layer for user management operations
"""

import bcrypt
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import structlog

from dao.user_dao import UserDAO
from models import User, UserStatus, UserRole
from constants.api_constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from constants.database_constants import STATUS_ACTIVE, STATUS_INACTIVE, STATUS_PENDING

logger = structlog.get_logger()

class UserService:
    """Service layer for user management with proper database operations"""
    
    def __init__(self):
        self.user_dao = UserDAO()
    
    def _validate_password_strength(self, password: str) -> bool:
        """Validate password strength requirements"""
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters long")
        
        if not re.search(r'[A-Z]', password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            raise ValueError("Password must contain at least one number")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")
        
        # Check for common weak passwords
        weak_passwords = [
            "123456789012", "password123!", "admin123456!", 
            "welcome123!", "qwerty123456!"
        ]
        if password.lower() in [p.lower() for p in weak_passwords]:
            raise ValueError("Password is too common, please choose a stronger password")
        
        return True
    
    def _hash_password(self, password: str) -> str:
        """Hash password with bcrypt"""
        salt = bcrypt.gensalt(rounds=12)  # 12 rounds for security
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create new user with password validation and hashing"""
        try:
            # Validate password strength
            if 'password' in user_data:
                self._validate_password_strength(user_data['password'])
                user_data['password_hash'] = self._hash_password(user_data['password'])
                del user_data['password']  # Remove plain password
            
            # Validate email format
            email = user_data.get('email', '').lower()
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                raise ValueError("Invalid email format")
            
            user_data['email'] = email
            user_data['status'] = user_data.get('status', STATUS_ACTIVE)
            
            # Create user in database
            db_user = await self.user_dao.create_user(user_data)
            
            # Convert to User model
            user = User(
                id=db_user['id'],
                email=db_user['email'],
                name=db_user['name'],
                password_hash=db_user['password_hash'],  # Include password_hash
                status=UserStatus(db_user['status']),
                created_at=db_user['created_at'],
                updated_at=db_user['updated_at'],
                last_login_at=db_user.get('last_login_at'),
                email_verified_at=db_user.get('email_verified_at')
            )
            
            logger.info("User created successfully", user_id=user.id, email=user.email)
            return user
            
        except ValueError as e:
            logger.error("User creation validation failed", error=str(e))
            raise e
        except Exception as e:
            logger.error("User creation failed", error=str(e))
            raise e
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            db_user = await self.user_dao.get_user_by_id(user_id)
            if not db_user:
                return None
            
            return User(
                id=db_user['id'],
                email=db_user['email'],
                name=db_user['name'],
                password_hash=db_user['password_hash'],  # Include password_hash
                status=UserStatus(db_user['status']),
                created_at=db_user['created_at'],
                updated_at=db_user['updated_at'],
                last_login_at=db_user.get('last_login_at'),
                email_verified_at=db_user.get('email_verified_at')
            )
            
        except Exception as e:
            logger.error("Failed to get user by ID", error=str(e), user_id=user_id)
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            db_user = await self.user_dao.get_user_by_email(email)
            if not db_user:
                return None
            
            return User(
                id=db_user['id'],
                email=db_user['email'],
                name=db_user['name'],
                password_hash=db_user['password_hash'],  # Include password_hash
                status=UserStatus(db_user['status']),
                created_at=db_user['created_at'],
                updated_at=db_user['updated_at'],
                last_login_at=db_user.get('last_login_at'),
                email_verified_at=db_user.get('email_verified_at')
            )
            
        except Exception as e:
            logger.error("Failed to get user by email", error=str(e), email=email)
            return None
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user information"""
        try:
            # Handle password update with validation
            if 'password' in update_data:
                self._validate_password_strength(update_data['password'])
                update_data['password_hash'] = self._hash_password(update_data['password'])
                del update_data['password']
            
            # Handle email update with validation
            if 'email' in update_data:
                email = update_data['email'].lower()
                if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                    raise ValueError("Invalid email format")
                update_data['email'] = email
            
            # Update user in database
            success = await self.user_dao.update_user(user_id, update_data)
            if not success:
                return None
            
            # Add 100ms delay for ClickHouse consistency (read-after-write fix)
            import asyncio
            await asyncio.sleep(0.1)
            
            # Return updated user
            return await self.get_user_by_id(user_id)
            
        except ValueError as e:
            logger.error("User update validation failed", error=str(e), user_id=user_id)
            raise e
        except Exception as e:
            logger.error("User update failed", error=str(e), user_id=user_id)
            raise e
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        try:
            return await self.user_dao.delete_user(user_id)
        except Exception as e:
            logger.error("User deletion failed", error=str(e), user_id=user_id)
            return False
    
    async def list_users(self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE, 
                        status_filter: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """List users with pagination"""
        try:
            # Validate pagination parameters
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)
            offset = max(0, (page - 1) * page_size)
            
            # Get users and count
            db_users = await self.user_dao.list_users(page_size, offset, status_filter, search)
            total_count = await self.user_dao.count_users(status_filter, search)
            
            # Convert to User models
            users = []
            for db_user in db_users:
                user = User(
                    id=db_user['id'],
                    email=db_user['email'],
                    name=db_user['name'],
                    password_hash=db_user['password_hash'],
                    status=UserStatus(db_user['status']),
                    created_at=db_user['created_at'],
                    updated_at=db_user['updated_at'],
                    last_login_at=db_user.get('last_login_at'),
                    email_verified_at=db_user.get('email_verified_at')
                )
                users.append(user)
            
            return {
                "users": users,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            return {
                "users": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""
        try:
            db_user = await self.user_dao.get_user_by_email(email)
            if not db_user:
                return None
            
            # Check password
            if not self._verify_password(password, db_user['password_hash']):
                return None
            
            # Update last login
            await self.user_dao.update_user(db_user['id'], {
                'last_login_at': datetime.now(timezone.utc)
            })
            
            return User(
                id=db_user['id'],
                email=db_user['email'],
                name=db_user['name'],
                password_hash=db_user['password_hash'],
                status=UserStatus(db_user['status']),
                created_at=db_user['created_at'],
                updated_at=db_user['updated_at'],
                last_login_at=datetime.now(timezone.utc),
                email_verified_at=db_user.get('email_verified_at')
            )
            
        except Exception as e:
            logger.error("Authentication failed", error=str(e), email=email)
            return None
    
    # User invitation methods (replacing memory storage)
    async def create_invitation(self, email: str, tenant_id: str, role: UserRole, 
                               invited_by: str) -> Dict[str, Any]:
        """Create user invitation with database storage"""
        try:
            import secrets
            
            # Generate secure invitation token
            invitation_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            
            invitation_data = {
                'email': email,
                'tenant_id': tenant_id,
                'role': role.value,
                'invited_by': invited_by,
                'invitation_token': invitation_token,
                'expires_at': expires_at
            }
            
            invitation_id = await self.user_dao.create_invitation(invitation_data)
            
            return {
                "invitation_id": invitation_id,
                "invitation_token": invitation_token,
                "invitation_expires": expires_at,
                "invited_email": email,
                "email": email,  # For backward compatibility with tests
                "tenant_id": tenant_id,
                "role": role.value
            }
            
        except Exception as e:
            logger.error("Failed to create invitation", error=str(e))
            raise e
    
    async def validate_invitation(self, token: str, email: str) -> Optional[Dict[str, Any]]:
        """Validate invitation token and email match"""
        try:
            invitation = await self.user_dao.get_invitation_by_token(token)
            if not invitation:
                return None
            
            # Check if expired
            if invitation['expires_at'] < datetime.now(timezone.utc):
                return None
            
            # Check if email matches
            if invitation['email'].lower() != email.lower():
                return None
            
            # Check if already accepted
            if invitation['status'] != STATUS_PENDING:
                return None
            
            return invitation
            
        except Exception as e:
            logger.error("Failed to validate invitation", error=str(e))
            return None
    
    async def accept_invitation(self, invitation_id: str) -> bool:
        """Accept invitation and mark as used"""
        try:
            return await self.user_dao.update_invitation_status(invitation_id, STATUS_ACTIVE)
        except Exception as e:
            logger.error("Failed to accept invitation", error=str(e))
            return False
    
    # =================================================================
    # SESSION MANAGEMENT METHODS
    # =================================================================
    
    async def create_session(self, user: User, ip_address: str, user_agent: str) -> Dict[str, Any]:
        """Create new user session"""
        try:
            from authn_authz_middleware import generate_jwt_token
            from models import UserSession, SessionStatus
            
            # Generate JWT token
            session_data = generate_jwt_token(user.id)
            
            # Create session object
            session = UserSession(
                user_id=user.id,
                session_token=session_data["access_token"],
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=session_data["expires_at"]
            )
            
            # Save session to database via DAO
            session_db_data = {
                "id": session.id,
                "user_id": session.user_id,
                "session_token": session.session_token,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "expires_at": session.expires_at,
                "status": session.status.value,
                "customer_id": "platform"
            }
            
            # Save session via DAO
            await self.user_dao.create_session(session_db_data)
            
            logger.info("Session created", user_id=user.id, session_id=session.id)
            return session_data
            
        except Exception as e:
            logger.error("Failed to create session", user_id=user.id, error=str(e))
            raise e
    
    async def revoke_session(self, token: str) -> bool:
        """Revoke user session by token"""
        try:
            # Revoke session via DAO
            success = await self.user_dao.revoke_session(token)
            if success:
                logger.info("Session revoked successfully", token=token[:8] + "...")
            else:
                logger.warning("Session revocation failed - session not found", token=token[:8] + "...")
            return success
            
        except Exception as e:
            logger.error("Failed to revoke session", token=token[:8] + "...", error=str(e))
            return False
    
    async def get_user_by_reset_token(self, reset_token: str) -> Optional[User]:
        """Get user by password reset token"""
        try:
            if not reset_token:
                return None
                
            # Query user with valid reset token via DAO
            # Get user by reset token via DAO
            user_data = await self.user_dao.get_user_by_reset_token(reset_token)
            
            if user_data:
                return User(
                    id=user_data["id"],
                    email=user_data["email"],
                    name=user_data["name"],
                    password_hash=user_data["password_hash"],
                    status=UserStatus(user_data["status"]),
                    created_at=user_data.get("created_at"),
                    updated_at=user_data.get("updated_at"),
                    last_login_at=user_data.get("last_login_at"),
                    email_verified_at=user_data.get("email_verified_at")
                )
                
            return None
            
        except Exception as e:
            logger.error("Failed to get user by reset token", reset_token=reset_token[:8] + "...", error=str(e))
            return None
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        try:
            return await self.user_dao.get_user_sessions(user_id)
        except Exception as e:
            logger.error("Failed to get user sessions", user_id=user_id, error=str(e))
            return []
    
    async def revoke_user_session(self, user_id: str, session_id: str) -> bool:
        """Revoke a specific user session"""
        try:
            return await self.user_dao.revoke_user_session(user_id, session_id)
        except Exception as e:
            logger.error("Failed to revoke user session", user_id=user_id, session_id=session_id, error=str(e))
            return False
    
    async def revoke_session_by_id(self, session_id: str, user_id: str) -> bool:
        """Revoke session by ID (alias for revoke_user_session)"""
        return await self.revoke_user_session(user_id, session_id)
    
    async def revoke_all_user_sessions(self, user_id: str, except_session_id: str = None) -> int:
        """Revoke all user sessions except optionally the current one"""
        try:
            return await self.user_dao.revoke_all_user_sessions(user_id, except_session_id)
        except Exception as e:
            logger.error("Failed to revoke all user sessions", user_id=user_id, error=str(e))
            return 0
    
    async def revoke_all_user_sessions_except_current(self, user_id: str, current_token: str) -> int:
        """Revoke all user sessions except the current one (by token)"""
        try:
            # Get current session ID from token
            # TODO: Add method to get session ID from token
            # For now, use the session token as the exception
            return await self.revoke_all_user_sessions(user_id, current_token)
        except Exception as e:
            logger.error("Failed to revoke all sessions except current", user_id=user_id, error=str(e))
            return 0
    
    async def validate_session(self, token: str) -> Optional[User]:
        """Validate session token and return user"""
        try:
            from authn_authz_middleware import decode_jwt_token
            from models import SessionStatus
            
            # Let JWT decode exceptions propagate (they raise HTTPException)
            payload = decode_jwt_token(token)
            user_id = payload["user_id"]
            
            # Check session exists and is active using DAO
            try:
                session_data = await self.user_dao.get_session(token)
                
                if session_data and session_data["status"] == SessionStatus.ACTIVE.value:
                    # Update last activity in database asynchronously without blocking
                    import asyncio
                    asyncio.create_task(self._update_session_activity_async(token))
                    
                    user = await self.get_user_by_id(user_id)
                    if user and user.status == UserStatus.ACTIVE:
                        return user
                        
            except Exception as e:
                logger.error("Failed to validate session in database", token=token[:8] + "...", error=str(e))
            
            # If session not found or inactive, return None (will be handled by middleware)
            return None
            
        except Exception as e:
            logger.error("Session validation error", token=token[:8] + "...", error=str(e))
            return None
    
    async def _update_session_activity_async(self, token: str):
        """Update session activity asynchronously without blocking validation"""
        try:
            await self.user_dao.update_session_activity(token)
            logger.debug("Session activity updated asynchronously", token=token[:8] + "...")
        except Exception as e:
            logger.error("Failed to update session activity asynchronously", token=token[:8] + "...", error=str(e))
    
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
        """Get user's roles for specific tenant (includes platform admin roles)"""
        try:
            return await self.user_dao.get_user_tenant_roles(user_id, tenant_id)
        except Exception as e:
            logger.error("Failed to get user tenant roles via service", 
                       user_id=user_id, tenant_id=tenant_id, error=str(e))
            return []
    
    async def list_platform_admin_users(self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
        """List users with platform admin roles"""
        try:
            # Validate pagination parameters
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)
            offset = max(0, (page - 1) * page_size)
            
            # Get platform admin users
            db_users = await self.user_dao.list_platform_admin_users(page_size, offset)
            
            # Convert to User models
            users = []
            for db_user in db_users:
                user = User(
                    id=db_user['id'],
                    email=db_user['email'],
                    name=db_user['name'],
                    password_hash=db_user['password_hash'],
                    status=UserStatus(db_user['status']),
                    created_at=db_user['created_at'],
                    updated_at=db_user['updated_at'],
                    last_login_at=db_user.get('last_login_at'),
                    email_verified_at=db_user.get('email_verified_at')
                )
                users.append(user)
            
            # Count total platform admins (simplified for now)
            total_count = len(users)  # This is not perfect but avoids an extra query
            
            return {
                "users": users,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
            }
            
        except Exception as e:
            logger.error("Failed to list platform admin users", error=str(e))
            return {
                "users": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
    
    async def verify_user_has_platform_roles(self, user_id: str) -> bool:
        """Verify if user has any platform admin roles"""
        try:
            return await self.user_dao.verify_user_has_platform_roles(user_id)
        except Exception as e:
            logger.error("Failed to verify platform roles", error=str(e), user_id=user_id)
            return False
    
    async def check_super_admin_count(self) -> int:
        """Count active super admin users to prevent lockout"""
        try:
            return await self.user_dao.count_super_admins()
        except Exception as e:
            logger.error("Failed to count super admins", error=str(e))
            return 0
    
    async def revoke_all_user_sessions_for_security(self, user_id: str, current_session_token: str = None) -> int:
        """Revoke all user sessions for security purposes"""
        try:
            return await self.user_dao.revoke_all_user_sessions(user_id, current_session_token)
        except Exception as e:
            logger.error("Failed to revoke all sessions for security", error=str(e), user_id=user_id)
            return 0