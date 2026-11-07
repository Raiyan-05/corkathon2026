from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, PasswordField, SubmitField
from wtforms.validators import InputRequired, DataRequired, EqualTo, NumberRange, Length

def clean(value):
    return value.strip() if isinstance(value, str) else value

def clean_code(value):
    value = clean(value)
    return value.upper() if value else value


class LoginForm(FlaskForm):
    airport_code = StringField("Airport Code:", filters=[clean_code], validators=[InputRequired(), Length(min=3, max=4)])
    employee_id = IntegerField("Employee ID:", validators=[InputRequired(), NumberRange(min=100000000, max=999999999)])
    password = PasswordField("Password:", validators=[InputRequired()])
    submit = SubmitField("Log in")

class RegistrationForm(LoginForm):
    f_name = StringField("First Name:", filters=[clean], validators=[DataRequired()])
    s_name = StringField("Last Name:", filters=[clean], validators=[DataRequired()])
    confirm_password = PasswordField("Confirm Password:", validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField("Register")
