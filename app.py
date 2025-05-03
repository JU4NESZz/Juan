from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from eth_account import Account

# RPC de Fuji Testnet
RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"
CHAIN_ID = 43113

# Conexión JJ
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise RuntimeError("No se pudo conectar a Fuji RPC")

app = FastAPI(title="Avalanche Loan API",
              description="API para validar préstamos sin comisiones en Fuji Testnet",
              version="1.0.0")

class TxRequest(BaseModel):
    private_key: str
    to: str
    value_ether: float

@app.post("/validate", summary="Valida y envia transacción")
def validate_tx(req: TxRequest):
    try:
        # Validar formato de la dirección de destino
        if not w3.is_address(req.to):
            raise HTTPException(status_code=400, detail="Dirección de destino inválida")

        # Preparar cuenta y transacción
        acct = Account.from_key(req.private_key)
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = {
            "nonce": nonce,
            "to": req.to,
            "value": w3.to_wei(req.value_ether, "ether"),
            "gas": 21000,
            "gasPrice": w3.eth.gas_price,
            "chainId": CHAIN_ID
        }
        # Firmar y enviar
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        # Esperar confirmación y obtener recibo
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "tx_hash": w3.to_hex(tx_hash),
            "status": receipt.status,
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber
        }
    except ValueError as ve:
        # Captura errores como clave privada inválida o fondos insuficientes (a veces se manifiestan como ValueError)
        raise HTTPException(status_code=400, detail=f"Error de valor: {str(ve)}")
    except Exception as e:
        # Captura otros errores generales (conexión, timeouts, etc.)
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.get("/health", summary="Chequea estado de conexión")
def health_check():
    return {"connected": w3.is_connected()}

# Para arrancar:
# uvicorn app:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
