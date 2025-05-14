import requests
import logging

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom exception for handling errors
class CustomException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(self.message)

# Crawl class for logging in and validating login
class Crawl:
    def __init__(self, user_id, password):
        logger.info(f"Initializing crawler for user_id: {user_id}")
        self._session = requests.Session()
        self._id = user_id
        self._pw = password

    # Method for handling GET and POST requests
    def _get_response(self, method, url, headers=None, body=None):
        logger.info(f"Making {method} request to {url}")
        if headers is None:
            headers = {}
        if body is None:
            body = {}
        try:
            if method == 'POST':
                response = self._session.post(url, headers=headers, data=body)
            else:
                response = self._session.get(url, headers=headers)
            response.raise_for_status()  # Raises an exception for 4xx/5xx responses
            return response
        except requests.RequestException as e:
            logger.error(f'Error in HTTP request: {str(e)}')
            raise CustomException(500, f'Error in HTTP request: {str(e)}')

    # Login method that checks if the login is successful
    def _login(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        body = {'username': self._id, 'password': self._pw}
        login_url = 'https://cyber.anyang.ac.kr/login/index.php'  # Login URL
        logger.info(f"Logging in with user_id: {self._id}")
        response = self._get_response('POST', login_url, headers, body)

        # Check if the login was successful by inspecting the response URL
        if 'login' in response.url or 'error' in response.url:
            logger.error("Login Failed")
            raise CustomException(300, 'Login Failed')

        logger.info("Login successful")
        return "Login successful"

    # Main method to execute the login process
    def crawl_user(self):
        try:
            logger.info("Starting crawl_user process")
            return self._login()  # Only perform login and return success message
        except CustomException as e:
            if e.code == 301:
                logger.info("Cookie expired, trying to re-login")
                return self._login()
            else:
                raise e
