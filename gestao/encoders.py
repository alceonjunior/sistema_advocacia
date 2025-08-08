# gestao/encoders.py

import json
from decimal import Decimal
from datetime import date

class DecimalEncoder(json.JSONEncoder):
    """
    Encoder JSON customizado para lidar com tipos de dados não serializáveis
    padrão, como Decimal e date.
    """
    def default(self, o):
        if isinstance(o, Decimal):
            # Converte objetos Decimal para string para manter a precisão
            return str(o)
        if isinstance(o, date):
            # Converte objetos date para o formato de string ISO (YYYY-MM-DD)
            return o.isoformat()
        # Para qualquer outro tipo, usa o comportamento padrão
        return super().default(o)