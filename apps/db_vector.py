import openai
import os
import streamlit as st
from streamlit_chat import message

from langchain import OpenAI
from langchain.chains import VectorDBQAWithSourcesChain
from lib import schema, vdb
from sqlalchemy import create_engine


DATABASES = ['adventure_works']


def app():
    openai.api_key = os.environ['OPENAI_KEY'] or Exception(
        'No OPENAI_KEY found in environment')
    st.set_page_config(page_title="Postgres Assistant", page_icon=":robot:")
    st.header("Postgres Assistant")

    if 'engine' not in st.session_state:
        st.session_state['engine'] = None

    if 'db_name' not in st.session_state:
        st.session_state['db_name'] = None

    if 'vdb' not in st.session_state:
        st.session_state['vdb'] = None

    if "generated" not in st.session_state:
        st.session_state["generated"] = []

    if "past" not in st.session_state:
        st.session_state["past"] = []

    st.title('Database Assistant')
    with st.sidebar.expander(label='Database Setting'):
        db_name = st.selectbox('Select your database', DATABASES)
        if st.session_state['engine'] is None or st.session_state['db_name'] != db_name:
            st.session_state['engine'] = create_engine(
                f'postgresql://postgres:postgres@localhost/{db_name}')

        if st.button('Regenerate Schema'):
            with st.session_state['engine'].connect() as con:
                schemas = schema.load_from_db(con)
                schema.save_to_file(db_name, schemas)
                vdb.build(db_name)
                st.session_state['vdb'] = vdb.load(db_name)

            st.write(f'Database schema for {db_name} generated')
        else:
            if schema.exists(db_name) and vdb.exists(db_name):
                st.session_state['vdb'] = vdb.load(db_name)

    if not st.session_state['vdb']:
        st.write(
            f'Database schema for {db_name} not loaded. Please "Regenerate Schema" first')
        return

    chain = VectorDBQAWithSourcesChain.from_llm(llm=OpenAI(
        temperature=0, model_name='gpt-3.5-turbo'), vectorstore=st.session_state['vdb'])
    st.write(f'Database schema for {db_name} loaded')

    input = st.text_area('Please ask questions for the database',  key='input')
    if st.button('Ask'):
        st.write(f'Your question: {input}. Thinking...')
        result = chain({'question': input})
        output = f'Answer: {result["answer"]}\n'

        st.session_state["generated"].append(output)
        st.session_state['past'].append(input)

    if st.session_state["generated"]:
        for i in range(len(st.session_state["generated"]) - 1, -1, -1):
            message(st.session_state["generated"][i], key=str(i))
            message(st.session_state["past"][i],
                    is_user=True, key=str(i) + "_user")


if __name__ == "__main__":
    app()
