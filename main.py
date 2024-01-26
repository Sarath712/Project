import os

from flask import Flask, render_template, request, jsonify
import psycopg2
import plotly.graph_objects as go
import pandas as pd

app = Flask(__name__)

conn = psycopg2.connect(
    user="postgres",
    password="12345",
    host="localhost",
    port="5433",
    database="postgres"
)
cursor = conn.cursor()

@app.route('/')
def home():
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    data_names = [row[0] for row in cursor.fetchall()]
    return render_template('Home.html', data_names=data_names)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        data_name = request.form['dataName']
        csv_file = request.files['csvFile']

        file_path = os.path.join('uploads', csv_file.filename)
        csv_file.save(file_path)

        table_name = f'"{data_name}"'

        try:
            create_table_query, absolute_path = generate_create_table_query(file_path, table_name)
            cursor.execute(create_table_query)
            conn.commit()

            cursor.execute(f"COPY {table_name} FROM '{absolute_path}' DELIMITER ',' CSV HEADER;")
            conn.commit()

            return f"Data {data_name} uploaded successfully."
        except Exception as e:
            print(e)
            conn.rollback()
            return 'Internal Server Error', 500
        finally:
            os.remove(file_path)

    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    data_names = [row[0] for row in cursor.fetchall()]

    return render_template('Upload_List.html', data_names=data_names)

def generate_create_table_query(file_path, table_name):
    absolute_path = os.path.abspath(file_path)
    with open(absolute_path, 'r') as csv_file:
        first_line = csv_file.readline().strip()
        columns = [f'"{col}" VARCHAR(255)' for col in first_line.split(',')]

    columns_definition = ', '.join(columns)
    create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_definition});"
    return create_table_query, absolute_path

@app.route('/plot', methods=['GET', 'POST'])
def plot():
    try:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        data_names = [row[0] for row in cursor.fetchall()]

        if request.method == 'POST':
            data_name = request.form.get('dataName', '')
            print(f"Received data_name: {data_name}")

            if not data_name:
                return 'Data name is required', 400  # Bad Request

            columns = get_column_names(data_name)
            print(f"Columns in /plot route: {columns}")

            x_column = request.form.get('xColumn', '')
            operation = request.form.get('operation', '')

            if operation:
                cursor.execute(f"SELECT {operation}({x_column}) FROM {data_name}")
                result = cursor.fetchone()[0]
            else:
                result = None

            cursor.execute(f"SELECT {x_column}, y_column FROM {data_name} WHERE y_column IS NOT NULL")
            data = cursor.fetchall()

            return render_template('Plot.html', data_names=data_names, columns=columns, data_name=data_name,
                                   x_column=x_column, y_column='y_column', data=data, result=result)

    except Exception as e:
        print(f"Error in /plot route: {e}")
        conn.rollback()
        return 'Internal Server Error', 500

    return render_template('Plot.html', data_names=data_names, error_message='Invalid request')

def get_column_names(data_name):
    try:
        data_name = request.form.get('dataName', '')
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{data_name}'")
        columns = [row[0] for row in cursor.fetchall()]
        return jsonify(columns)
    except Exception as e:
        print(f"Error fetching columns for {data_name}: {e}")
        return []

def perform_computation(data_name, column_name, operation):
    cursor.execute(f"SELECT {column_name} FROM {data_name};")
    data = [row[0] for row in cursor.fetchall()]

    if operation == 'min':
        result = min(data)
    elif operation == 'max':
        result = max(data)
    elif operation == 'sum':
        result = sum(data)
    else:
        result = None

    return result

def generate_plot(data_name, x_column, y_column):
    cursor.execute(f"SELECT {x_column}, {y_column} FROM {data_name};")
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=[x_column, y_column])

    fig = go.Figure(data=go.Scatter(x=df[x_column], y=df[y_column], mode='markers'))
    plot_url = fig.to_html(full_html=False)

    return plot_url

if __name__ == '__main__':
    app.run(debug=True)
