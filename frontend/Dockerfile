FROM node:20-alpine

WORKDIR /app

# Copy dependency configs
COPY package.json package-lock.json* ./

# Install dependencies (ignoring optional engine-specific packages for speed)
RUN npm install

# Copy application files
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
