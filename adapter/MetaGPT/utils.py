NAME_PROFILE_MAP = {
    'Mike': 'Team Leader',
    'Alex': 'Engineer',
    'David': 'DataAnalyst',
    'Bob': 'Architect',
    'Alice': 'Product Manager'
}

PROFILE_NAME_MAP = {
    'Team Leader': 'Mike',
    'Engineer': 'Alex',
    'DataAnalyst': 'David',
    'Architect': 'Bob',
    'Product Manager': 'Alice'
}

def get_profile(name: str):
    return NAME_PROFILE_MAP[name]

def get_name(profile: str):
    return PROFILE_NAME_MAP[profile]