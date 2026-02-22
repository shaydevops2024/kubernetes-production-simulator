FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY app.js     /usr/share/nginx/html/app.js
COPY style.css  /usr/share/nginx/html/style.css
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
