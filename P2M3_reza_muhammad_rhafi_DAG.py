'''
=================================================
Milestone 3

Nama  : Reza Muhammad Rhafi
Batch : FTDS-023-HCK

Program ini dibuat untuk melakukan automatisasi transform dan load data dari PostgreSQL ke ElasticSearch.
=================================================
'''


import pandas as pd
import numpy as np
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresHook
from datetime import datetime, timedelta

from elasticsearch import Elasticsearch

# default parameter
default_args = {
    'owner': 'Reza',
    'retry': None,
    'start_date': datetime(2024, 11, 1)
}

# Function extract
def extract(**context):
    '''
        Fungsi ini bertujuan untuk mengambil data mentah dari PostgreSQL dan menyimpannya dalam file CSV.

        Parameters:
        **context: dictionary - konteks dari Airflow untuk menggunakan XCom dalam menyimpan atau mengambil informasi antar task.

        Return:
        Tidak ada return nilai langsung, namun path file data mentah disimpan menggunakan XCom.

        Contoh penggunaan:
        Fungsi ini akan otomatis dipanggil oleh task `extract_data` dalam pipeline.
    '''
    #koneksi ke database
    source_hook = PostgresHook(postgres_conn_id='postgres_airflow')
    source_conn = source_hook.get_conn()

    # baca data di sql
    data_raw = pd.read_sql('SELECT * FROM table_m3', source_conn)

    #simpan dalam bentuk csv
    path = '/opt/airflow/dags/P2M3_reza_muhammad_rhafi_data_raw.csv'
    data_raw.to_csv(path, index=False)

    # export path data kotor
    context['ti'].xcom_push(key='raw_data_path',value=path)

# function cleaning
def transform(**context):
    '''
        Fungsi ini bertujuan untuk melakukan proses cleaning dan transformasi pada data mentah.

        Parameters:
        **context: dictionary - konteks dari Airflow untuk menggunakan XCom dalam mengambil path file mentah dan menyimpan path file yang sudah bersih.

        Proses yang dilakukan:
        - Menghapus data yang memiliki nilai kosong (missing values).
        - Menghapus data yang duplikat.
        - Menormalkan nama kolom agar konsisten (menggunakan huruf kecil, mengganti spasi dengan underscore, dan menghapus simbol tak alfanumerik).
        - Menyimpan data yang sudah bersih ke dalam file CSV.

        Contoh penggunaan:
        Fungsi ini akan otomatis dipanggil oleh task `transform_data` dalam pipeline.
    '''

    # ambil konteks task instance
    ti = context['ti']

    # ambil path data mentah
    data_path = ti.xcom_pull(task_ids='extract_data', key='raw_data_path')

    # buka sebagai dataframe
    data_raw = pd.read_csv(data_path)

    #cleaning 
    data_raw = data_raw.dropna() # handling missing value
    data_raw = data_raw.drop_duplicates() # drop duplicate

    # 2. Normalisasi nama kolom
    data_raw.columns = data_raw.columns.str.lower()  # Semua huruf kecil
    data_raw.columns = data_raw.columns.str.replace(' ', '_')  # Ganti spasi dengan underscore
    data_raw.columns = data_raw.columns.str.replace(r'[^\w\s]', '')  # Menghapus simbol selain alphanumeric dan space
    data_clean = data_raw

    # simpan data clean
    path = '/opt/airflow/dags/P2M3_reza_muhammad_rhafi_data_clean.csv'
    data_clean.to_csv(path, index=True, index_label="row_id") 

    # export path data kotor
    context['ti'].xcom_push(key='clean_data_path',value=path)



# function load data
def load(**context):

    '''
        Fungsi ini bertujuan untuk memuat data yang sudah bersih ke Elasticsearch.

        Parameters:
        **context: dictionary - konteks dari Airflow untuk menggunakan XCom dalam mengambil path file data bersih.

        Proses yang dilakukan:
        - Membuka file CSV yang berisi data bersih dan memuatnya ke dalam dataframe.
        - Membuat koneksi ke Elasticsearch.
        - Memasukkan data ke Elasticsearch dengan iterasi per baris.

        Contoh penggunaan:
        Fungsi ini akan otomatis dipanggil oleh task `load_data` dalam pipeline.
    '''
    
    # ambil konteks task instance
    ti = context['ti']

    # ambil path data mentah
    data_path = ti.xcom_pull(task_ids='transform_data', key='clean_data_path')

    # load jadi dataframe
    data_clean = pd.read_csv(data_path)

    # buat koneksi ke elasticsearch
    # es = Elasticsearch('http://elasticsearch:9200')
    es = Elasticsearch(hosts=["http://elasticsearch:9200"])
    
    if not es.ping():
        print('CONNECTION FAILED')

    # load datanya
    for i, row in data_clean.iterrows():
        doc=row.to_json()
        res = es.index(index = 'milestone_3', doc_type = 'doc', body = doc)

# definisi dag
with DAG(
    'milestone_3',
    description = 'pipeline milestone 3',
    schedule_interval = '10,20,30 9 * * 6',  #  tugas akan dijalankan setiap 10 menit antara pukul 09:00 hingga 09:30 setiap hari Sabtu
    default_args = default_args,
    catchup = False) as dag:

    # task extract
    extract_data = PythonOperator(
        task_id = 'extract_data',
        python_callable=extract,
        provide_context=True
    )

    # task transform
    transform_data = PythonOperator(
        task_id = 'transform_data',
        python_callable=transform,
        provide_context=True
    )
    
    # task load
    load_data = PythonOperator(
        task_id = 'load_data',
        python_callable = load,
        provide_context = True
    )

extract_data >> transform_data >> load_data

