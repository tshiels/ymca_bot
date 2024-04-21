from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import datetime, time, logging

from selenium.webdriver.support.wait import IGNORED_EXCEPTIONS

def setup_log():
    log = logging.getLogger('log')
    log.setLevel(logging.INFO)
    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(r'C:\Users\Tommy\Desktop\_ymca.log')
    log_format = logging.Formatter(fmt='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    c_handler.setFormatter(log_format)
    f_handler.setFormatter(log_format)
    log.addHandler(c_handler)
    log.addHandler(f_handler)

    return log

def timer(timer):
    while timer:
        mins, secs = divmod(timer, 60)
        hrs, mins = divmod(mins, 60)
        time_str = '{:02d}:{:02d}:{:02d}'.format(hrs, mins, secs)
        print('T- %s' % time_str, end='\r')
        timer -= 1
        time.sleep(1)

class swim_session():
    def __init__(self, start_time, end_time, element):
        self.start_time = start_time
        self.end_time = end_time
        self.element = element

class ymca_bot():
    def __init__(self):
        self.driver = None
        #self.driver.maximize_window()
        self.target_date = ''
        self.result = ''
    
    def init(self):
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options)

    def restart(self):
        try:
            self.driver.close()
        except:
            pass
        # if you need to restart, probably don't want to wait for the next day (wait for midnight(0,1))
        self.run_attempts(now=True)
    
    def run_attempts(self, now=False):
        if not now:
            self.wait_for_midnight(0, 1)
        midnight = datetime.datetime.now()
        self.init()
        self.login()
        attempt = 0
        while self.result not in ['B', 'W']:
            log.info('======================================')
            log.info('Starting attempt %d...' % (attempt + 1))
            log.info('======================================')
            attempt += 1
            if (attempt > 0):
                self.driver.get('https://www.ymcasf.org/swim-schedule')
            self.select_target_date()
            self.find_valid_sessions()
            now = datetime.datetime.now()
            if now >= midnight + datetime.timedelta(hours=2):
                print('2 hours no success')
                return

    def run_test(self):
        self.init()
        self.login()
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bw-session')))
        el = self.driver.find_elements_by_class_name('bw-session')
        self.find_open_slots(el)

    def run(self):
        self.wait_for_midnight(1, 1)
        self.init()
        self.login()
        self.select_target_date()
        self.find_valid_sessions()
        #self.driver.quit()

    def reserve(self, slots, is_available):
        availability = 'open' if is_available else 'waitlist'
        for slot in slots:
            log.info('Attempting to reserve %s - %s %s slot...' % (slot.start_time, slot.end_time, availability))
            res_btn = slot.element.find_element_by_css_selector('button[class="bw-widget__signup-now bw-widget__cta"]')
            res_btn.click()
            WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it('mindbody_branded_web_cart_modal'))
            #WebDriverWait(self.driver, 20).until(EC.invisibility_of_element((By.CSS_SELECTOR, 'main[class="main"]')))
            # might have to change to driver.execute_script("arguments[0].click();", element) <-- THAT WORKED to CLOSE MODAL DIALOGUE
            # https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen
            next_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/main/a')))
            next_btn.click()
            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, 'thank__header')))
                log.info('Reservation successful -- %s -- %s.' % (availability.upper(), slot.start_time))
                return True
            except TimeoutException:
                # FIX ME: might have to reload page
                log.info('Unable to make reservation.')
                self.driver.switch_to.default_content()
                continue
        return False

    def find_open_slots(self, sessions):
        available = []
        waitlist = []
        animation = "|/-\\"
        idx = 0
        for session in sessions:
            print('Searching for available sessions...' + animation[idx % len(animation)], end="\r")
            idx += 1
            time.sleep(0.1)
            avail_div = session.find_element_by_css_selector('div.bw-session__availability')
            try:
                availability = avail_div.find_element_by_tag_name('span').get_attribute('textContent')
            except NoSuchElementException:
                availability = 'None'
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'time.hc_starttime')))
            start_time = session.find_element_by_css_selector('time.hc_starttime').text
            end_time = session.find_element_by_css_selector('time.hc_endtime').text
            if availability != 'Waitlist Only' and availability != 'None':
                print('', end='\r')
                #log.info('Found open slot at %s              ' % (start_time))
                if start_time > '04:00 PM' and start_time < '05:00 PM':
                    available.append(swim_session(start_time, end_time, session))
            elif availability == 'Waitlist Only':
                #log.info('Found waitlist slot at %s          ' % (start_time))
                if start_time > '04:00 PM' and start_time < '05:00 PM':
                    waitlist.append(swim_session(start_time, end_time, session))
        if len(available) > 0:
            result = self.reserve(available, True)
            if result == True: self.result = 'B'
        else:
            log.info('Did not find any open slots 4:00-5:00 PM')
            result = False
            self.result = 'F'
        if len(waitlist) > 0 and result == False:
            result = self.reserve(waitlist, False)
            if result == True: self.result = 'W'
        if result == False:
            log.info('Did not find any waitlist slots 4:00-5:00 PM.')
            self.result = 'F'
        # if len(open) + len(waitlist) == 0, and len(sessions) != 0, then you're too early, unless everything is booked already
        # ...unlikely if it's midnight
        #if len(sessions) > 0 and (len(available) + len(waitlist) == 0):
        #    log.info('Detected unavailable valid sessions...trying again in 1 minute.')


    def select_target_date(self):
        today = datetime.datetime.now()
        two_days_from_now = today + datetime.timedelta(days=2)
        self.target_date = two_days_from_now.strftime('%Y-%m-%d')
        try:
            date_btn = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'span[data-bw-startdate="%s"]' % self.target_date)))
            date_btn.click()
            log.info('Found target date.')
        except (StaleElementReferenceException, NoSuchElementException) as e:
            print("...trying again")
            try:
                date_btn = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-bw-startdate="%s"]' % self.target_date)))
                date_btn.click()
                log.info('Found target date.')
            except:
                log.info(e)
    
    def is_stonestown(self, session):
        for i in range(10):
            try: 
                val = session.find_element_by_css_selector('div.bw-session__staff').text == 'Pool Stonestown'
                val2 = session.get_attribute('data-bw-widget-visit-type') == '2036'
                return val and val2
            except:
                pass

    def find_valid_sessions(self):
        #FIX ME: sometimes number of sessions is wrong, doesn't get all sessions, maybe sleep, presence_of_all_elements_located
        # ^ caused by select_target_date not actually clicking, is grabbing sessions for today's date not 2 days from now
        # ^ FIXED
        try:
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bw-session')))
        except TimeoutException:
            try:
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bw-session')))
            except TimeoutException:
                log.info('No sessions available on target date.')
        cur_date = self.driver.find_element_by_class_name('bw-calendar__day--current')
        span = cur_date.find_element_by_tag_name('span')
        if span.get_attribute('data-bw-startdate') != (datetime.datetime.now() + \
            datetime.timedelta(days=2)).strftime('%Y-%m-%d'):
            log.info('Mismatched date...retrying')
            self.select_target_date()
            # might have to just call the function again...num_attempts
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bw-session')))
        sessions = self.driver.find_elements_by_class_name('bw-session')
        #time.sleep(0.4)
        #sessions = self.driver.find_elements_by_class_name('bw-session')
        log.info('Found %d sessions for target date %s.' % (len(sessions), self.target_date))
        valid_sessions = [session for session in sessions if self.is_stonestown(session)]
        log.info('Found %d lap swim sessions at Stonestown.' % len(valid_sessions))
        if len(valid_sessions) > 0:
            self.find_open_slots(valid_sessions)
        else:
            log.info("No available lap swim sessions for target date/time.")
            
    def login(self):
        self.driver.get('https://www.ymcasf.org/swim-schedule')
        acc_btn = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="148809"]/div[1]/button[2]')))
        acc_btn.click()
        WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it('mindbody_branded_web_cart_modal'))
        #try:
        email_in = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="mb_client_session_username"]')))
        pw_in = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="mb_client_session_password"]')))
        email_in.send_keys('email')
        pw_in.send_keys('password')
        WebDriverWait(self.driver, 20).until(EC.invisibility_of_element((By.ID, "pre-load-spinner")))
        sign_in = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[class="cta signin__cta"]')))
        sign_in.click()
        self.driver.switch_to.default_content()
        self.driver.get('https://www.ymcasf.org/swim-schedule')

    def wait_for_midnight(self, start_time, day_offset):
        now = datetime.datetime.now()
        sleep_time = (datetime.datetime(now.year, now.month, now.day + day_offset, start_time, 0, 0) - now)
        secs = sleep_time.seconds
        sleep = now + sleep_time
        if sleep < now:
            return
        log.info('Waiting for %s' % sleep.strftime('%I:%M %p'))
        timer(secs)
        

if __name__ == '__main__':
    log = setup_log()
    bot = ymca_bot()
    try:
        bot.run_attempts()
    except Exception as e:
        log.error(e)
        log.info('Encountered error, restarting...')
        bot.restart()
