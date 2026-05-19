FROM nginx:alpine

# Copy index.html to the default Nginx public directory
COPY index.html /usr/share/nginx/html/index.html.template

# Create a startup script to perform environment variable substitution
RUN echo '#!/bin/sh' > /docker-entrypoint.d/40-substitute-env-vars.sh && \
    echo 'envsubst "\$BACKEND_URL" < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html' >> /docker-entrypoint.d/40-substitute-env-vars.sh && \
    chmod +x /docker-entrypoint.d/40-substitute-env-vars.sh

# The default BACKEND_URL for local testing if not provided
ENV BACKEND_URL=http://localhost:8080

EXPOSE 80
