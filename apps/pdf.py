import os
import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.chains import ChatVectorDBChain
from lib.vdb import Vdb
from lib import loader
from pathlib import Path


PDF_PATH = 'data/pdf'


def app():
    st.set_page_config(page_title="PDF helper", page_icon=":robot:")
    st.header("PDF helper")

    if 'name' not in st.session_state:
        st.session_state['name'] = None

    if 'vdb' not in st.session_state:
        st.session_state['vdb'] = None

    if "history" not in st.session_state:
        st.session_state["history"] = []

    with st.sidebar.expander(label='PDF Setting'):
        uploaded = st.file_uploader('Upload your PDF file', type=['pdf'])
        if uploaded is not None:
            data = uploaded.getvalue()
            with open(f'{PDF_PATH}/{uploaded.name}', 'wb') as f:
                f.write(data)

        pdf_names = [Path(f).stem for f in os.listdir(
            PDF_PATH) if f.endswith('.pdf')]
        name = st.selectbox('Select PDF file', pdf_names)

        vdb = Vdb(PDF_PATH, name)
        if st.button('Generate Vector DB'):
            if not vdb.exists():
                data = loader.pdf(f'{PDF_PATH}/{name}.pdf')
                vdb.build(data)
                st.write(f'Vector database for {name}.pdf generated')

            st.session_state['name'] = name
            st.session_state['vdb'] = vdb.load()
            st.session_state["history"] = []

        if name != st.session_state['name']:
            if vdb.exists():
                st.session_state['name'] = name
                st.session_state['vdb'] = vdb.load()
                st.session_state["history"] = []

    if not st.session_state['vdb']:
        st.session_state['name'] = name
        st.write(
            f'Vector database for {name}.pdf not loaded. Please "Generate Vector DB" first')
        return

    chain = ChatVectorDBChain.from_llm(llm=ChatOpenAI(
        temperature=0, model_name='gpt-3.5-turbo'), vectorstore=st.session_state['vdb'])
    st.write(f'Vector database for {name}.pdf loaded')

    input = st.text_area('Please ask questions for the PDF',  key='input')
    if st.button('Ask'):
        with st.spinner('Thinking super hard...'):
            result = chain(
                {'question': input, 'chat_history': st.session_state["history"]})
            output = result["answer"]

            c = st.container()
            c.write(f'### Q: {input}')
            c.write(output)

            st.session_state["history"].append((input, output))

    with st.sidebar.expander(label='History'):
        if st.session_state["history"]:
            history = st.session_state["history"][-1:-6:-1]
            for i in range(len(history)):
                c = st.container()
                (q, a) = history[i]
                c.write(q)
                c.write(a)


if __name__ == "__main__":
    app()
