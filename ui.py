import streamlit as st  
import requests, json

avatars ={
    'user':'https://static.vecteezy.com/system/resources/thumbnails/002/318/271/small_2x/user-profile-icon-free-vector.jpg',
    'assistant':'https://miro.medium.com/v2/resize:fit:1400/1*ChXf6m80xpdTqpEL1xu5qg.jpeg'
}

def load_css():
    with open('./styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def get_persons():
    res = requests.get('http://127.0.0.1:8000/api/get_persons/')
    x = res.json()
    st.session_state.persons = x

def load_person(url,name):
    data = {
        "url":url,
        "name":name
    }
    
    res = requests.post('http://127.0.0.1:8000/api/load_personality/', json=data)
    st.toast(res.json()["message"])
    
    st.session_state.chat = True
    if name != st.session_state.curr_person:
        st.session_state.reset_chat = True
    
    st.session_state.curr_person = name

@st.experimental_dialog("Add Personality")
def add_person():
    st.write('Add details about the Person:')
    name = st.text_input("Name of Person")
    url = st.text_input("Website with the Person's data")
    data = {
        "url":url,
        "name":name
    }

    if st.button('Add'):
        res = requests.put('http://127.0.0.1:8000/api/add_person/', json=data)
        st.toast(res.json()["message"])

def handleChat(query, model):
    data = {
        "query":query,
        "model":model
    }
    st.session_state.messages.append({"role":"user", "content":query})
    response = requests.post('http://127.0.0.1:8000/api/get_response/', json=data)
    st.session_state.messages.append({"role":"assistant", "content":response.json()["message"]})

def main():
    st.set_page_config('Sawaal jawab',layout='wide')
    load_css()
    
    if 'curr_person' not in st.session_state:
        st.session_state.curr_person = ''

    if 'chat' not in st.session_state:
        st.session_state.chat = False

    if 'messages' not in st.session_state:
        st.session_state.messages = []
   
    if 'reset_chat' not in st.session_state:
        st.session_state.reset_chat = False

    with st.sidebar:
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            if st.button('🔄', help='Reload Data.'):
               get_persons()
        with col2:
            if st.button('🆕', help='Add Personality.'):
                add_person()
        with col3:
            if( st.button('🏠', help="Home.")):
                st.session_state.chat = False
        
        if 'persons' in st.session_state:
            p = st.session_state.persons
            urls = p['url']
            names = p['name']

            for u, n in zip(urls, names):
                st.button(label=n, key=u, on_click=load_person,args=[u,n])
    
    # home page
    if st.session_state.chat == False:        
        st.title('Sawaal Jawab.')
        st.markdown("<div className = 'subtitle'>Add a Personality, or select one from the sidebar to start!</div>", unsafe_allow_html=True)
    
    if st.session_state.chat:
        col1, col2 = st.columns([0.8,0.2])
        with col1:
            st.title(st.session_state.curr_person)
        with col2:
            model = st.selectbox('Model', ['LLAMA', 'MIXTRAL'])
        
        c = st.container(height=350, border=True)
        if st.session_state.reset_chat:
            st.session_state.messages = []
            st.session_state.reset_chat = False

        q = st.chat_input("Your message:")
        if q:
            handleChat(q,model)

        if st.session_state.messages:
            for message in st.session_state.messages:
                c.chat_message(name = message['role'], avatar=avatars[message['role']]).write(message['content'])
    
if __name__ == "__main__":
    main()