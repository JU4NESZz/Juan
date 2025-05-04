from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field # Importar Field
from typing import Optional # Importar Optional
from web3 import Web3
from eth_account import Account

# RPC de Fuji Testnet
RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"
CHAIN_ID = 43113

# Conexión JJ
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise RuntimeError("No se pudo conectar a Fuji RPC")

app = FastAPI(title="Avalanche Loan Logging API", # Título actualizado
              description="API para registrar eventos de crédito en Fuji Testnet (Avalanche C-Chain)", # Descripción actualizada
              version="1.0.1") # Versión actualizada

class TxRequest(BaseModel):
    private_key: str
    to: str
    value_ether: float = Field(default=0.0) # Valor por defecto 0.0
    data: Optional[str] = None # Campo opcional para datos adicionales

@app.post("/log_event", summary="Registra un evento en la blockchain") # Endpoint renombrado y summary actualizado
def log_event_tx(req: TxRequest): # Función renombrada
    try:
        # Validar formato de la dirección de destino
        if not w3.is_address(req.to):
            raise HTTPException(status_code=400, detail="Dirección 'to' inválida")

        # Preparar cuenta
        try:
            acct = Account.from_key(req.private_key)
        except ValueError:
             raise HTTPException(status_code=400, detail="Clave privada inválida")

        nonce = w3.eth.get_transaction_count(acct.address)

        # Preparar transacción
        tx = {
            "from": acct.address, # Añadir 'from' es buena práctica aunque se infiere de la key
            "nonce": nonce,
            "to": req.to,
            "value": w3.to_wei(req.value_ether, "ether"), # Usará 0 si no se especifica
            # "gas": 21000, # Eliminado para permitir estimación automática
            "gasPrice": w3.eth.gas_price,
            "chainId": CHAIN_ID
        }

        # Añadir datos si se proporcionan
        if req.data:
            tx["data"] = req.data.encode('utf-8') # Codificar data como bytes UTF-8

        # Estimar gas (opcional pero recomendado si hay datos)
        try:
            estimated_gas = w3.eth.estimate_gas(tx)
            tx["gas"] = estimated_gas
        except Exception as estimate_error:
             # Si la estimación falla (ej. fondos insuficientes para gas), devolver error
             raise HTTPException(status_code=400, detail=f"Error estimando gas: {str(estimate_error)}")


        # Firmar y enviar
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        # Esperar confirmación y obtener recibo
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "message": "Evento registrado exitosamente en blockchain.",
            "tx_hash": w3.to_hex(tx_hash),
            "status": receipt.status,
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber,
            "logged_data": req.data # Devolver los datos enviados para confirmación
        }
    except ValueError as ve:
        # Captura errores como clave privada inválida o problemas de formato (aunque algunos ya se capturan antes)
        raise HTTPException(status_code=400, detail=f"Error de valor: {str(ve)}")
    except Exception as e:
        # Captura otros errores generales (conexión, timeouts, fondos insuficientes no capturados antes, etc.)
        print(f"Error detallado: {type(e).__name__} - {e}") # Loguear error para depuración
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.get("/health", summary="Chequea estado de conexión")
def health_check():
    return {"connected": w3.is_connected()}

# Para arrancar:
# uvicorn app:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
