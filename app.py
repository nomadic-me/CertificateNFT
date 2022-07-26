import os
import json
from web3 import Account
#from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3 import Web3
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import requests

load_dotenv()

# Create a W3 Connection
w3 = Web3(Web3.HTTPProvider(os.getenv("WEB3_PROVIDER_URI")))
private_key = os.getenv("PRIVATE_KEY")
contract_address = os.getenv("SMART_CONTRACT_ADDRESS")

def generate_account(w3,private_key):
    account = Account.privateKeyToAccount(private_key)
    return account

# Set up Pinata Headers
json_headers = {
    "Content-Type":"application/json",
    "pinata_api_key": os.getenv("PINATA_API_KEY"),
    "pinata_secret_api_key": os.getenv("PINATA_SECRET_API_KEY")
}

file_headers = {
    "pinata_api_key": os.getenv("PINATA_API_KEY"),
    "pinata_secret_api_key": os.getenv("PINATA_SECRET_API_KEY")
}

def convert_data_to_json(content):
    data = {"pinataOptions":{"cidVersion":1}, 
            "pinataContent":content }
    return json.dumps(data)

def pin_file_to_ipfs(data):
    r = requests.post("https://api.pinata.cloud/pinning/pinFileToIPFS",
                      files={'file':data},
                      headers= file_headers)
    print(r.json())
    ipfs_hash = r.json()["IpfsHash"]
    return ipfs_hash

def pin_json_to_ipfs(json):
    r = requests.post("https://api.pinata.cloud/pinning/pinJSONToIPFS",
                      data=json,
                      headers= json_headers)
    print(r.json())
    ipfs_hash = r.json()["IpfsHash"]
    return ipfs_hash

def pin_cert(cert_name, cert_file,**kwargs):
    # Pin certificate picture to IPFS
    ipfs_file_hash = pin_file_to_ipfs(cert_file.getvalue())

    # Build our NFT Token JSON
    token_json = {
       "name": cert_name,
       "image": f"ipfs.io/ipfs/{ipfs_file_hash}"
    }

    # Add extra attributes if any passed in
    token_json.update(kwargs.items())

    # Add to pinata json to be uploaded to Pinata
    json_data = convert_data_to_json(token_json)

    # Pin the real NFT Token JSON
    json_ipfs_hash = pin_json_to_ipfs(json_data)

    return json_ipfs_hash, token_json


# Pull in Ethereum Account - Used for signing transactions
account = generate_account(w3,private_key)
st.write("Loaded Account Address: ", account.address)
st.write("Smart Contract Address: ", contract_address)

######################################################################
## Load the contract
######################################################################

@st.cache(allow_output_mutation=True)
def load_contract():
    with open(Path("./contracts/compiled/certificate_abi.json")) as file:
        certificate_abi = json.load(file)

    contract_address = os.getenv("SMART_CONTRACT_ADDRESS")

    cert_contract = w3.eth.contract(address=contract_address,
                    abi=certificate_abi)

    return cert_contract            

contract = load_contract()

student_account = st.text_input("Enter Student's Account Address: ", value="0x9182b74A7ED5A9b92f7113bE0415927411256426")

######################################################################
## Streamlit Inputs
######################################################################
st.markdown("## Create the Certificate")

cert_name = st.text_input("Enter the name of a student: ")
university_name = st.text_input("Name of University: ", value="University of Toronto")
class_name = st.text_input("Enter the class name: ", value="Fintech Bootcamp")
cert_date = st.text_input("Date of completion: ", value="07-25-2022")
cert_details = st.text_input("Certificate Details: ", value="Certificate of Completion")

# Upload the Certificate Picture File
file = st.file_uploader("Upload a Certificate", type=["png","jpeg"])


######################################################################
## Button to Award the Certificate
######################################################################

if st.button("Award Certificate"):

    cert_ipfs_hash,token_json = pin_cert(cert_name,file, university=university_name, class_name=class_name, 
            date_of_completion = cert_date, details=cert_details)

    cert_uri = f"ipfs.io/ipfs/{cert_ipfs_hash}"

    nonce = w3.eth.get_transaction_count(account.address)
 
    tx = contract.functions.mint(student_account,cert_uri).buildTransaction({
        'chainId':4,
        'gas':20000000,
        'nonce':nonce
    })

    st.write("Raw TX: ", tx)

    signed_tx = account.sign_transaction(tx)

    st.write("Signed TX Hash: ", signed_tx.rawTransaction)

    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    # This generally works on the mainnet - Rinkeby, not so much
    receipt = w3.eth.waitForTransactionReceipt(tx_hash,timeout=300)      

    st.write("Transaction mined")
    st.write(dict(receipt))

    st.write("You can view the pinned metadata file with the following IPFS Gateway Link")
    st.markdown(f"[Cert IPFS Gateway Link] (https://{cert_uri})")
    st.markdown(f"[Cert IPFS Image Link] (https://{token_json['image']})")