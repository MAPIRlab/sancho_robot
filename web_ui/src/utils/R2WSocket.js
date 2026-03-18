import { v4 as uuidv4 } from "uuid";

const CHUNK_MESSAGE_TYPE = {
    CHUNK: "CHUNK",
}

const MESSAGE_TYPE = {
    MESSAGE: "MESSAGE",
    TOPIC: "TOPIC",
};

export default class R2WSocket {
    constructor(url) {
        this.socket = new WebSocket(url); // Usar reconnecting websocket
        this.encoder = new TextEncoder();
        this.buffers = {};

        this.socket.onopen = (event) => this.onopen?.(event);
        this.socket.onclose = (event) => this.onclose?.(event);
        this.socket.onerror = (error) => this.onerror?.(error);

        this.socket.onmessage = (event) => {
            let chunk_message;
            try {
                chunk_message = JSON.parse(event.data);
            } catch (e) {
                console.log("ERROR ON JSON PARSE ON CHUNK MESSAGE", e, event.data);
                return;
            }            
            
            const { id, type, chunk_index, final, data } = chunk_message;
            if (type === CHUNK_MESSAGE_TYPE.CHUNK) {
                //const sizeKB = (this.encoder.encode(event.data).length / 1024).toFixed(2);
                //console.log(`Chunk received ${chunk_index} (final: ${final}) — ${sizeKB} KB`);
                
                if (!this.buffers[id]) this.buffers[id] = []
                this.buffers[id].push({ index: chunk_index, data });

                if (final) {
                    const fullStr = this.buffers[id].sort((a, b) => a.index - b.index).map(c => c.data).join("");
                    delete this.buffers[id];
                    this._onmessage(fullStr);
                }
            }
        };
    }

    _onmessage(event) {
        let r2w_message;
        try {
            r2w_message = JSON.parse(event);
        } catch (e) {
            console.log("ERROR ON JSON PARSE ON R2WSocket", e, event);
            return;
        }            
        
        const { type, data } = r2w_message;
        if (type === MESSAGE_TYPE.MESSAGE) {
            this.onmessage(JSON.parse(data));
        } else if  (type === MESSAGE_TYPE.TOPIC) {
            this.ontopic(data);
        }
    }

    _msgToChunks(fullStr, maxChunkSize = 256000) {
        const chunks = [];

        const id = uuidv4();
        for (let i = 0; i < fullStr.length; i += maxChunkSize) {
            chunks.push({
                id: id,
                type: CHUNK_MESSAGE_TYPE.CHUNK,
                chunk_index: Math.floor(i / maxChunkSize),
                final: (i + maxChunkSize) >= fullStr.length,
                data: fullStr.slice(i, i + maxChunkSize)
            });
        }
    
        return chunks;
    }

    send(message) {
        try {
            const fullStr = JSON.stringify({
                type: MESSAGE_TYPE.MESSAGE,
                data: message,
            });
        
            const chunks = this._msgToChunks(fullStr);
            chunks.forEach(chunk => {
                const chunkStr = JSON.stringify(chunk);
                const sizeKB = (this.encoder.encode(chunkStr).length / 1024).toFixed(2);
        
                //console.log(`Sending chunk ${chunk.chunk_index} (final: ${chunk.final}) — ${sizeKB} KB`);
                this.socket.send(chunkStr);
            });

            return true;
        } catch (e) {
            return false;
        }
    }
    
    close() {
        this.socket.close();
    }
}
