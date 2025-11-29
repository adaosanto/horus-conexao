#!/bin/bash

# Verifica se docker compose está instalado
# if ! [ -x "$(command -v docker compose)" ]; then
#   echo 'Error: docker compose is not installed.' >&2
#   exit 1
# fi

COMPOSE="docker compose -f compose.yaml"

# Lista de domínios que o certificado SAN vai cobrir
domains=(api.horusystem.com.br)
rsa_key_size=4096
data_path="./certbot"
email="adaosantosn@outlook.com" # Altamente recomendado usar email válido
staging=0 # 1 para teste (staging), 0 para produção

# Primeiro domínio (usado para criar e remover o certificado dummy)
primary_domain="${domains[0]}"

# Verifica se já existe certificado
if [ -d "$data_path" ]; then
  read -p "Existing data found for ${primary_domain}. Continue and replace existing certificate? (y/N) " decision
  if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
    exit
  fi
fi

# Baixa parâmetros SSL recomendados se não existir
if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  mkdir -p "$data_path/conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
  echo
fi

# Cria certificado dummy para permitir que o nginx suba antes do Let's Encrypt
echo "### Creating dummy certificate for ${primary_domain} ..."
path="/etc/letsencrypt/live/${primary_domain}"
mkdir -p "$data_path/conf/live/${primary_domain}"
$COMPOSE run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1 \
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot
echo

# Sobe o nginx
echo "### Starting nginx ..."
$COMPOSE up --force-recreate -d nginx
echo

# Remove certificado dummy
echo "### Deleting dummy certificate for ${primary_domain} ..."
$COMPOSE run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/${primary_domain} && \
  rm -Rf /etc/letsencrypt/archive/${primary_domain} && \
  rm -Rf /etc/letsencrypt/renewal/${primary_domain}.conf" certbot
echo

# Monta lista de domínios para o Certbot
echo "### Requesting Let's Encrypt certificate for ${domains[*]} ..."
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

# Argumento de email
case "$email" in
  "") email_arg="--register-unsafely-without-email" ;;
  *) email_arg="--email $email" ;;
esac

# Modo staging se necessário
if [ $staging != "0" ]; then staging_arg="--staging"; fi

# Solicita o certificado SAN
$COMPOSE run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $email_arg \
    $domain_args \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal" certbot
echo

# Recarrega o nginx para usar o novo certificado
echo "### Reloading nginx ..."
$COMPOSE exec nginx nginx -s reload