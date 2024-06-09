from flask import Flask, jsonify, render_template, request, send_file
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import datetime
import pandas as pd

import disc_space as ds

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bme280.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class BME280(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receive_time = db.Column(db.DateTime, nullable=False)
    temp = db.Column(db.Float, nullable=True)
    hum = db.Column(db.Float, nullable=True)
    pres = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "receive_time": self.receive_time,
            "temp": self.temp,
            "hum": self.hum,
            "pres": self.pres,
        }
    

def column_names():
    empty = BME280()
    return [key for key in empty.to_dict().keys()]


def temp_len():
    cols = [col for col in column_names() if "temp" in col]
    return len(cols)


def hum_len():
    cols = [col for col in column_names() if "hum" in col]
    return len(cols)


def pres_len():
    cols = [col for col in column_names() if "pres" in col]
    return len(cols)


def sensors_len():
    return temp_len() + hum_len() + pres_len()


with app.app_context():
    db.create_all()


@app.route('/')
@app.route('/index')
def home():
    num_of_values = 5
    con = sqlite3.connect("instance/bme280.db")
    df = pd.read_sql_query(f"SELECT * from BME280 ORDER BY id DESC LIMIT {num_of_values}", con)
    con.close()

    last_values = [df[column].values.tolist() for column in df.columns]

    return render_template("index.html",
                           date_year=datetime.date.today().year,
                           num_of_values=num_of_values,
                           num_of_elements=len(last_values),
                           headers=df.columns.values,
                           last_values=last_values,
                           space=ds.db_size(),
                           free_space=ds.free_space())


@app.route("/last-24hours-pressure")
def plot_last_24hours_pressure():
    try:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        con = sqlite3.connect("instance/bme280.db")

        cols = [col for col in column_names() if "pres" in col]
        cols_str = ",".join(cols)
        print(cols)
        df = pd.read_sql_query(f"SELECT receive_time, {cols_str} from BME280 WHERE receive_time >= '{yesterday}'", con)
        con.close()
    except Exception as e:
        return f"Error! {e}"
    else:
        print(df.columns)
        x_data = df[df.columns[0]].values.tolist()
        y_data = [df[df.columns[i]].values.tolist() for i in range(1, (len(cols)+1))]
        return render_template("data_plot_multiple.html",
                               date_year=datetime.date.today().year,
                               x_data=x_data,
                               y_data=y_data,
                               legend=[sensor.replace("_", " ") for sensor in df.columns[1:].values.tolist()],
                               title="last 24 hours pressure data from all sensors",
                               x_label="time",
                               y_label="Pressure [hPa]")


@app.route("/last-24hours-humidity")
def plot_last_24hours_humidity():
    try:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        con = sqlite3.connect("instance/bme280.db")

        cols = [col for col in column_names() if "hum" in col]
        cols_str = ",".join(cols)
        print(cols)
        df = pd.read_sql_query(f"SELECT receive_time, {cols_str} from BME280 WHERE receive_time >= '{yesterday}'", con)
        con.close()
    except Exception as e:
        return f"Error! {e}"
    else:
        print(df.columns)
        x_data = df[df.columns[0]].values.tolist()
        y_data = [df[df.columns[i]].values.tolist() for i in range(1, (len(cols)+1))]
        return render_template("data_plot_multiple.html",
                               date_year=datetime.date.today().year,
                               x_data=x_data,
                               y_data=y_data,
                               legend=[sensor.replace("_", " ") for sensor in df.columns[1:].values.tolist()],
                               title="last 24 hours humidity data from all sensors",
                               x_label="time",
                               y_label="humidity [%]")

@app.route("/temp-24hours")
def plot_temp_24hours():
    try:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        con = sqlite3.connect("instance/bme280.db")

        cols = [col for col in column_names() if "temp" in col]
        cols_str = ",".join(cols)
        print(cols)
        df = pd.read_sql_query(f"SELECT receive_time, {cols_str} from BME280 WHERE receive_time >= '{yesterday}'", con)
        con.close()
    except Exception as e:
        return f"Error! {e}"
    else:
        print(df.columns)
        x_data = df[df.columns[0]].values.tolist()
        y_data = [df[df.columns[i]].values.tolist() for i in range(1, (len(cols)+1))]
        return render_template("data_plot_multiple.html",
                               date_year=datetime.date.today().year,
                               x_data=x_data,
                               y_data=y_data,
                               legend=[sensor.replace("_", " ") for sensor in df.columns[1:].values.tolist()],
                               title="last 24 hours temperature data from all sensors",
                               x_label="time",
                               y_label="Temperature [\u2103]")
    

@app.route("/all", methods=["GET"])
def get_all_data():
    try:
        datatable = db.session.query(BME280).all()
    except Exception as e:
        print(e)
        return jsonify(response={"error": f"Reading BME280 data failed. Error description {e}"}), 404
    return jsonify(BME280=[data.to_dict() for data in datatable])


@app.route("/last", methods=["GET"])
def get_last_data():
    try:
        datatable = db.session.query(BME280).order_by(BME280.id.desc()).first()
    except Exception as e:
        print(e)
        return jsonify(response={"error": f"Reading BME280 data failed. Error description {e}"}), 404
    if datatable is not None:
        return jsonify(BME280=datatable.to_dict())
    else:
        return jsonify(responseget_last_data={"error": "No entries in database"}), 400
    

# download data as csv
@app.route('/download')
def download_data_csv():
    con = sqlite3.connect("instance/bme280.db")
    df = pd.read_sql_query("SELECT * from BME280 ", con)
    con.close()
    df.set_index("id", inplace=True)
    print(df.head())
    df.to_csv("instance/data.csv")
    return send_file("instance/data.csv", as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6969, debug=True)