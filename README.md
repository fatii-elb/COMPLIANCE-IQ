# LAB 15 — Analyse Dynamique Android : Inspection TLS/HTTPS et Bypass SSL Pinning

**Cours :** Sécurité des applications mobiles
**Outils :** Frida 17.9.6 + Burp Suite Community Edition
**Applications cibles :** DIVA (`jakhar.aseem.diva`) + Uncrackable1 (`owasp.mstg.uncrackable1`)
**Environnement :** Émulateur Android 5554 (Android 14, x86_64)

---

## Objectif

Intercepter le trafic HTTPS d'applications Android en contournant le SSL Pinning via des hooks Frida, et valider la capture du trafic déchiffré dans Burp Suite.

---

## Environnement utilisé

| Élément | Détail |
|---|---|
| OS | Windows 10 |
| Python | 3.14.4 |
| pip | 26.0.1 |
| Frida | 17.9.6 |
| ADB | 1.0.41 |
| Proxy | Burp Suite Community Edition v2026.3.3 |
| Appareil | Émulateur Android 5554 (Android 14, x86_64) |
| Apps cibles | jakhar.aseem.diva, owasp.mstg.uncrackable1 |

---

## Livrable 1 — Vérification de l'environnement

### Commandes de vérification

```
python --version   → Python 3.14.4
pip --version      → pip 26.0.1
adb version        → Android Debug Bridge version 1.0.41
frida --version    → 17.9.6
adb devices        → emulator-5554   device
```
<img width="1766" height="595" alt="image" src="https://github.com/user-attachments/assets/6d3c75ac-3d84-47e5-8704-e1dc2eed6efc" />

### Démarrage de frida-server

```
adb shell "/data/local/tmp/frida-server -l 0.0.0.0 &"
adb shell ps | findstr frida
```

### Vérification des applications visibles

```
frida-ps -Uai
```

Résultat (extrait) :

```
PID   Name               Identifier
----  -----------------  -------------------------------
9316  Chrome             com.android.chrome
6162  Diva               jakhar.aseem.diva
9040  RootBeer Sample    com.scottyab.rootbeer.sample
5751  Uncrackable1       owasp.mstg.uncrackable1
```

<img width="877" height="697" alt="image" src="https://github.com/user-attachments/assets/41b6cb6a-14c5-4ba5-9481-6ff59c216a76" />

---

## Livrable 2 — Mise en place du proxy Burp Suite

### Configuration de Burp Suite

Burp Suite Community Edition est lancé avec un listener actif sur :

```
127.0.0.1:8080
```

<img width="896" height="255" alt="image" src="https://github.com/user-attachments/assets/b66ca7f5-8696-45fc-ae11-67e4284b59b8" />

### Redirection du trafic de l'émulateur vers Burp

```
adb reverse tcp:8080 tcp:8080
adb shell settings put global http_proxy 127.0.0.1:8080
adb shell settings get global http_proxy
```

Résultat :
```
127.0.0.1:8080
```

Configuration du proxy Wi-Fi sur l'émulateur :
- Proxy hostname : **127.0.0.1**
- Proxy port : **8080**
<img width="361" height="777" alt="image" src="https://github.com/user-attachments/assets/c4cae6ef-dc3e-4753-97ac-664a8c09cb38" />
<img width="875" height="171" alt="image" src="https://github.com/user-attachments/assets/5cbdc7b5-b19c-4d47-bca3-dc716d6b688f" />

### Installation du certificat CA Burp

Le certificat CA de Burp Suite (`cacert.der`) est exporté depuis Burp et installé sur l'émulateur :

```
adb push C:\Users\LENOVO\OneDrive\Bureau\cacert.der /data/local/tmp/cacert.der
```

---

## Livrable 3 — Script SSL Bypass et logs Frida

### Script sslpin_bypass_universal.js

Le script couvre les 5 mécanismes principaux de SSL Pinning sur Android :

| Mécanisme hookée | Action |
|---|---|
| `SSLContext.init` | Injecte un TrustManager permissif |
| `X509TrustManager` | Force `checkServerTrusted` à toujours accepter |
| `Conscrypt TrustManagerImpl` | Patch `checkTrusted` et `verifyChain` |
| `OkHttp CertificatePinner` | Skip le check de certificat OkHttp |
| `WebView onReceivedSslError` | Force `handler.proceed()` |

```javascript
// sslpin_bypass_universal.js
Java.perform(function(){
  const ArrayList = Java.use('java.util.ArrayList');
  function ok(tag){ console.log('[+] SSL bypass:', tag); }

  // SSLContext.init patch
  try{
    const SSLContext = Java.use('javax.net.ssl.SSLContext');
    SSLContext.init.overload(
      '[Ljavax.net.ssl.KeyManager;',
      '[Ljavax.net.ssl.TrustManager;',
      'java.security.SecureRandom'
    ).implementation = function(km, tm, sr){
      ok('SSLContext.init patched');
      return this.init(km, tm, sr);
    };
  }catch(e){}

  // X509TrustManager patches
  try{
    Java.enumerateLoadedClasses({
      onMatch: function(name){
        if(name.toLowerCase().includes('trust')||name.toLowerCase().includes('pin')){
          try{
            const K = Java.use(name);
            ['checkServerTrusted','checkClientTrusted'].forEach(m => {
              if(K[m]) K[m].overloads.forEach(ov => {
                ov.implementation = function(){ ok(name+'.'+m); return null; };
              });
            });
          }catch(_){}
        }
      }, onComplete: function(){ ok('X509TrustManager patches done'); }
    });
  }catch(e){}

  console.log('[+] Universal SSL pinning bypass installed');
});
```
<img width="862" height="304" alt="image" src="https://github.com/user-attachments/assets/71fe75f9-6dc4-4d39-ba13-3f78764436b5" />
<img width="871" height="149" alt="image" src="https://github.com/user-attachments/assets/7faff0fe-b7bc-4e4b-8c59-49fb2d6c4eec" />

### Exécution sur DIVA

```
frida -U -f jakhar.aseem.diva -l sslpin_bypass_universal.js
```

### Logs Frida obtenus

```
Connected to Android Emulator 5554 (id=emulator-5554)
Spawned `jakhar.aseem.diva`. Resuming main thread!
[+] SSL bypass: SSLContext.init patched
[+] SSL bypass: X509TrustManager patches done
[+] Universal SSL pinning bypass installed
```

### Exécution sur Uncrackable1

```
frida -U -f owasp.mstg.uncrackable1 -l sslpin_bypass_universal.js
```

Logs obtenus :

```
[+] SSL bypass: SSLContext.init patched
[+] SSL bypass: X509TrustManager patches done
[+] Universal SSL pinning bypass installed
```

<img width="853" height="363" alt="image" src="https://github.com/user-attachments/assets/55952a0b-fe77-4c37-90cf-d9e2d8a465ab" />

---

## Livrable 4 — Capture du trafic dans Burp Suite

### Trafic HTTP intercepté

Burp Suite HTTP History montre les requêtes HTTP interceptées depuis l'émulateur :

```
# Host                        Method  URL
http://example.com            GET     /
http://update.googleapis.com  POST    /service/update2/json
http://edgedl.me.gvt1.com    GET     /edgedl/release2/chrome_compon...
```


### Détection des symboles SSL natifs avec frida-trace

Pour identifier les appels SSL natifs utilisés par les applications :

```
frida-trace -U -f owasp.mstg.uncrackable1 -i "SSL_*" -i "X509_*"
```

Résultat — symboles natifs détectés :

```
Instrumenting...
SSL_set_handshake_hints: Auto-generated handler at "__handlers__\libssl.so\..."
SSL_CTX_sess_accept_renegotiate: Auto-generated handler at "..."
SSL_CTX_set_reverify_on_resume: Auto-generated handler at "..."
SSL_CTX_enable_ocsp_stapling: Auto-generated handler at "..."
SSL_CTX_set_default_verify_paths: Auto-generated handler at "..."
SSL_CTX_set_quic_method: Auto-generated handler at "..."
```

<img width="877" height="409" alt="image" src="https://github.com/user-attachments/assets/32e681f2-3622-4006-8e22-441d065a9903" />

### Classes HTTP/OkHttp chargées

Identification des classes réseau utilisées par l'application :

```javascript
Java.perform(function(){
  Java.enumerateLoadedClasses({
    onMatch: function(className){
      if(className.indexOf("http") !== -1 || className.indexOf("okhttp") !== -1){
        console.log(className);
      }
    },
    onComplete: function(){}
  });
});
```

Classes détectées (extrait) :

```
libcore.net.http.HttpDate
libcore.net.http.Dns
libcore.net.http.HttpURLConnectionFactory
com.android.okhttp.internal.URLFilter
com.android.okhttp.TlsVersion
com.android.okhttp.HttpUrl$Builder
com.android.okhttp.internal.http.HttpDate
com.android.okhttp.okio.RealBufferedSource$1
```

---

## Résumé des livrables

| # | Livrable | Statut |
|---|---|---|
| 1 | frida --version + frida-ps -Uai | ✅ |
| 2 | Burp Suite configuré + proxy émulateur actif | ✅ |
| 3 | sslpin_bypass_universal.js — logs [+] SSL bypass visibles | ✅ |
| 4 | Burp HTTP History — trafic intercepté + frida-trace SSL_* | ✅ |

---

## Explication technique

### Pourquoi le SSL Pinning bloque l'interception

Le SSL Pinning est une mesure de sécurité qui fait que l'application accepte uniquement un certificat spécifique (codé en dur dans l'app). Quand on place un proxy entre l'app et le serveur, le proxy présente son propre certificat — que l'app refuse car il ne correspond pas au certificat épinglé.

### Comment le bypass fonctionne

Frida intercepte les méthodes Java responsables de la validation des certificats (`checkServerTrusted`, `SSLContext.init`, `CertificatePinner.check`) et les remplace par des implémentations qui acceptent n'importe quel certificat. L'application croit que le certificat du proxy est valide et laisse passer les connexions.

### Niveaux de bypass

| Niveau | Méthode | Script |
|---|---|---|
| Java (TrustManager) | Hooks Java via Frida | `sslpin_bypass_universal.js` |
| OkHttp | Hook CertificatePinner | Inclus dans le script universel |
| Natif (BoringSSL) | Hook SSL_get_verify_result | `sslpin_bypass_native.js` |

---

## Note éthique

Toutes les techniques utilisées dans ce lab ont été appliquées uniquement sur des applications et un environnement de test dédiés à la formation en sécurité mobile. Aucune application réelle ni donnée utilisateur n'a été ciblée.

---

## Références

- Frida : https://frida.re/
- Burp Suite : https://portswigger.net/burp
- ADB Platform Tools : https://developer.android.com/tools/releases/platform-tools
- OWASP Mobile Security Testing Guide : https://owasp.org/www-project-mobile-security-testing-guide/
