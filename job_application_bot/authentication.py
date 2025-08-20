
import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import Page

class Authentication:
    """Handles user authentication (sign-in and sign-up)"""

    def __init__(self, page: Page, user_data: Dict[str, Any]):
        """
        Initialize the Authentication handler.

        Args:
            page: The Playwright page object.
            user_data: The user's profile data.
        """
        self.page = page
        self.user_data = user_data

    async def handle_authentication(self, auth_type: int = 1) -> bool:
        """
        Handle authentication - tries signup first, then falls back to signin if needed.

        Args:
            auth_type: 1 for sign in, 2 for sign up (legacy parameter, now tries signup first regardless).
        """
        try:
            # First, try signup
            print("Attempting signup first...")
            signup_success = await self._handle_signup()
            
            if signup_success:
                # Wait a bit to see if signup was successful
                await asyncio.sleep(3)
                
                # Check if email and password fields are still present (indicating signup failed/needs signin)
                email_input = await self.page.query_selector('input[data-automation-id="email"]')
                password_input = await self.page.query_selector('input[data-automation-id="password"]')
                
                if email_input and password_input:
                    # Fields are still there, try signin instead
                    print("Email and password fields still present, attempting signin...")
                    return await self._handle_signin()
                else:
                    # Fields are gone, signup was successful
                    print("Signup appears to be successful")
                    return True
            else:
                # Signup failed, try signin
                print("Signup failed, attempting signin...")
                return await self._handle_signin()
                
        except Exception as e:
            print(f"Error during authentication: {e}")
            # Fallback to signin if anything goes wrong
            try:
                return await self._handle_signin()
            except Exception as signin_error:
                print(f"Error during signin fallback: {signin_error}")
                return False

    async def _handle_signup(self) -> bool:
        """Handle user sign up process"""
        try:
            personal_info = self.user_data.get('personal_information', {})
            email = personal_info.get('email', '')
            password = personal_info.get('password', '')

            # Fill email
            email_input = await self.page.query_selector('input[data-automation-id="email"]')
            if email_input:
                await email_input.fill(email)
                print(f"Filled email: {email}")

            # Fill password
            password_input = await self.page.query_selector('input[data-automation-id="password"]')
            if password_input:
                await password_input.fill(password)
                print("Filled password")

            # Fill verify password
            verify_password_input = await self.page.query_selector('input[data-automation-id="verifyPassword"]')
            if verify_password_input:
                await verify_password_input.fill(password)
                print("Filled verify password")

            # Check the create account checkbox
            checkbox = await self.page.query_selector('input[data-automation-id="createAccountCheckbox"]')
            if checkbox:
                checked = await checkbox.is_checked()
                if not checked:
                    await checkbox.check()
                print("Checked create account checkbox")

            # Click submit button
            await asyncio.sleep(1)
            submit_btn = await self.page.query_selector('div[aria-label="Create Account"]')
            if submit_btn:
                await submit_btn.click()
                print("Clicked create account submit button")
                return True
            return False
        except Exception as e:
            print(f"Error during signup: {e}")
            return False

    async def _handle_signin(self) -> bool:
        """Handle user sign in process"""
        try:
            # Click sign in link
            sign_in_link = await self.page.query_selector('button[data-automation-id="signInLink"]')
            if sign_in_link:
                await sign_in_link.click()
                print("Clicked sign in link")

            personal_info = self.user_data.get('personal_information', {})
            email = personal_info.get('email', '')
            password = personal_info.get('password', '')

            # Fill email
            email_input = await self.page.query_selector('input[data-automation-id="email"]')
            if email_input:
                await email_input.fill(email)
                print(f"Filled email: {email}")

            # Fill password
            password_input = await self.page.query_selector('input[data-automation-id="password"]')
            if password_input:
                await password_input.fill(password)
                print("Filled password")

            # Click submit button
            await asyncio.sleep(1)
            submit_btn = await self.page.query_selector('div[aria-label="Sign In"]')
            if submit_btn:
                await submit_btn.click()
                print("Clicked sign in submit button")
                return True
            return False
        except Exception as e:
            print(f"Error during signin: {e}")
            return False
