import random
import string

def generate_random_id(length=15):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))