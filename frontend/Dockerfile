FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host 0.0.0.0: Vite muss auf allen Interfaces lauschen, sonst ist der
# Server nur INNERHALB des Containers erreichbar (Host-Binding)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
