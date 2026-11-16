# openvpn-python-wrapper

Module Python qui lance OpenVPN avec `sudo`, attend que la connexion soit établie et permet de la couper. La classe `Vpn` expose `connect()`, `disconnect()`, `get_state()` et `get_last_error()`.

OpenVPN doit être installé. Comme le module lance `sudo openvpn` en arrière-plan, autorisez son exécution sans demande de mot de passe avec `sudo visudo -f /etc/sudoers.d/openvpn-python`. Ajoutez une règle adaptée à votre utilisateur et au chemin renvoyé par `command -v openvpn`, par exemple :

```sudoers
votre_utilisateur ALL=(root) NOPASSWD: /usr/sbin/openvpn
```

Installation et utilisation :

```bash
python -m pip install -e .
```

```python
from vpn import Vpn

vpn = Vpn()
resultat = vpn.connect(30, "utilisateur", "mot_de_passe", "/chemin/vers/client.ovpn")
print(resultat)  # "connected" ou un code d'erreur
vpn.disconnect()
```
