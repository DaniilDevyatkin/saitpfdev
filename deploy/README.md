# Развёртывание

Публикация устроена так: домашняя машина держит приложение и стенды, VDS принимает
внешний трафик и проксирует его домой через обратный SSH-туннель. Файлы сайта
остаются дома — на VDS нет ни одной страницы, только nginx и сертификат.

```
интернет → VDS 104.128.130.176 (nginx, TLS Let's Encrypt)
            ├── :443   → 127.0.0.1:18443 ─┐
            ├── :3100  → 127.0.0.1:13100 ─┤
            ├── :3301  → 127.0.0.1:13301 ─┤   SSH-туннель (исходящий, с дома)
            ├── :8200  → 127.0.0.1:18200 ─┤
            ├── :8300  → 127.0.0.1:18300 ─┤
            └── :8400  → 127.0.0.1:18400 ─┘
                                          └→ дом: 8110 витрина, 3100/3301 Игрушечки,
                                             8200 Карточки, 8300 Maison, 8400 TatuSait
```

Почему туннель, а не проброс портов: провайдер фильтрует входящие 80 и 443 на
домашнем подключении, поэтому сертификат Let's Encrypt на домашнем IP не выпустить.
На VDS 80-й открыт, там проверка домена проходит обычным способом.

## Файлы

| Файл | Куда |
|---|---|
| `deploy/nginx/devyatkinprod.conf` | `/etc/nginx/sites-available/devyatkinprod.conf` |
| `deploy/nginx/stands.conf` | `/etc/nginx/sites-available/stands.conf` |
| `deploy/systemd/portfolio-platform.service` | `~/.config/systemd/user/` |
| `deploy/systemd/portfolio-tunnel.service` | `~/.config/systemd/user/` |
| `deploy/systemd/portfolio-cert-renew.service` + `.timer` | `~/.config/systemd/user/` (для варианта с DNS-проверкой) |

Сертификат на VDS выпускается и продлевается самим certbot (`certbot --nginx`),
поэтому юниты продления в этом репозитории нужны только если сертификат
получается через DNS-01 на домашней машине.

## Порядок

1. На домашней машине: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`,
   скопировать `.env.stands` из закрытого хранилища, запустить юниты
   `portfolio-platform` и `portfolio-tunnel`, включить `loginctl enable-linger`.
2. На VDS: положить конфиги nginx, выпустить сертификат
   `certbot --nginx -d devyatkinprod.ru -d www.devyatkinprod.ru --redirect`,
   перезагрузить nginx.
3. В DNS домена: `A @ → 104.128.130.176` и `A www → 104.128.130.176`.

## Секреты

В репозиторий не попадают: `.env.stands` (JWT, пароли), `tls/` (ключи и
сертификаты), `data/` (базы SQLite). Всё это перечислено в `.gitignore`.
