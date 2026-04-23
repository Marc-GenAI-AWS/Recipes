"""
Configuration file for model query and answer update process.
"""

# AWS Configuration
AWS_REGION = "us-west-2"

# Model ARN mappings
MODEL_ARNS = {
    "lilly": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/jumpstart-dft-meta-textgeneration-l-20251015-005858",
    "uhg": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-212359",
    "money": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-215929",
    "gaming": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/bayer-value-prop-assistant-20251013-223013",
    "state": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/jumpstart-dft-meta-textgeneration-l-20251015-005858",
    "cheetah": "arn:aws:sagemaker:us-west-2:<AWS_ACCOUNT_ID>:endpoint/jumpstart-dft-meta-textgeneration-l-20251015-005858"
}

# File mappings based on usecase_map.py logic
FILE_MAPPINGS = {
    "lilly": {
        "questions": "event_files/questions/lilly_questions.txt",
        "answers": "event_files/70b_answers/lilly_patient_edu_responses_working.json"
    },
    "uhg": {
        "questions": "event_files/questions/uhg_questions.txt", 
        "answers": "event_files/70b_answers/uhg_patient_edu_responses_working.json"
    },
    "money": {
        "questions": "event_files/questions/money_laundering_questions.txt",
        "answers": "event_files/70b_answers/money_laundering_responses_working.json"
    },
    "gaming": {
        "questions": "event_files/questions/responsible_gaming_questions.txt",
        "answers": "event_files/70b_answers/responsible_gaming_responses.json"
    }
}

# Model parameters
MODEL_PARAMETERS = {
    "max_new_tokens": 2048,
    "temperature": 0.1,
    "top_p": 0.9,
    "do_sample": True
}

# Processing settings
DELAY_BETWEEN_QUERIES = 1  # seconds
CREATE_BACKUPS = True
