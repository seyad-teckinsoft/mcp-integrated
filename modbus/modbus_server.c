#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <modbus/modbus.h>
#include <sys/select.h>
#include <pthread.h>
#include <arpa/inet.h>

#define NB_REGISTERS 100
#define NB_COILS 10
#define MODBUS_PORT 502
#define IPC_PORT 1500

// ===================== SHARED DATA =====================
typedef struct {
    uint32_t counter;       // DWORD
    uint32_t write_value;   // DWORD
} system_data_t;

system_data_t g_data = {0};
pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;

// ===================== IPC =====================
int ipc_server_fd = -1;
int ipc_client_fd = -1;

void ipc_init()
{
    ipc_server_fd = socket(AF_INET, SOCK_STREAM, 0);

    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(IPC_PORT);
    addr.sin_addr.s_addr = INADDR_ANY;

    bind(ipc_server_fd, (struct sockaddr*)&addr, sizeof(addr));
    listen(ipc_server_fd, 1);

    printf("IPC server running on port %d...\n", IPC_PORT);

    ipc_client_fd = accept(ipc_server_fd, NULL, NULL);
    printf("PyQt connected!\n");
}

void ipc_process()
{
    if (ipc_client_fd < 0) return;

    char buffer[64];

    int len = recv(ipc_client_fd, buffer, sizeof(buffer)-1, MSG_DONTWAIT);

    if (len > 0) {
        buffer[len] = '\0';

        if (strncmp(buffer, "INC", 3) == 0) {
            pthread_mutex_lock(&g_lock);
            g_data.counter++;
            pthread_mutex_unlock(&g_lock);
        }
    }

    // send data
    char msg[64];
    pthread_mutex_lock(&g_lock);
    sprintf(msg, "%u,%u\n", g_data.counter, g_data.write_value);
    pthread_mutex_unlock(&g_lock);

    send(ipc_client_fd, msg, strlen(msg), MSG_DONTWAIT);
}

// ===================== MODBUS =====================

void update_modbus_from_system(modbus_mapping_t *mb)
{
    pthread_mutex_lock(&g_lock);

    // counter → 2 registers
    mb->tab_registers[0] = (g_data.counter >> 16) & 0xFFFF; // HIGH
    mb->tab_registers[1] = g_data.counter & 0xFFFF;         // LOW

    // write_value → 2 registers
    mb->tab_registers[2] = (g_data.write_value >> 16) & 0xFFFF;
    mb->tab_registers[3] = g_data.write_value & 0xFFFF;

    pthread_mutex_unlock(&g_lock);
}

void update_system_from_modbus(modbus_mapping_t *mb)
{
    pthread_mutex_lock(&g_lock);

    uint32_t new_value =
        ((uint32_t)mb->tab_registers[2] << 16) |
        mb->tab_registers[3];

    // 🔥 Print ONLY if changed
    if (new_value != g_data.write_value) {
        printf("PLC WRITE RECEIVED → DWORD: %u (0x%08X)\n",
               new_value, new_value);
    }

    g_data.write_value = new_value;

    pthread_mutex_unlock(&g_lock);
}

// ===================== HARDWARE SIM =====================

void *hardware_thread(void *arg)
{
    while (1) {
        sleep(1);

        pthread_mutex_lock(&g_lock);
        g_data.counter++;
        pthread_mutex_unlock(&g_lock);
    }
    return NULL;
}

// ===================== coils =====================
void update_coils_from_system(modbus_mapping_t *mb)
{ 
    int coil_01 = mb->tab_bits[0], coil_02 = mb->tab_bits[1], coil_03 = mb->tab_bits[2], coil_04 = mb->tab_bits[3], coil_05 = mb->tab_bits[4];
    pthread_mutex_lock(&g_lock);
    if (coil_01) {
        printf("Coil 00001 is ON\n");
    } else {
        printf("Coil 00001 is OFF\n");
    }
    if (coil_02) {
        printf("Coil 00002 is ON\n");
    } else {
        printf("Coil 00002 is OFF\n");
    }
    if(coil_03) {
            printf("Coil 00003 is ON\n");
        } else {
            printf("Coil 00003 is OFF\n");
        }
    mb->tab_bits[0] = coil_01; // Mirror coil 00001 to coil 00006
    mb->tab_bits[1] = coil_02; // Mirror coil 00002 to coil 00007
    mb->tab_bits[2] = coil_03; // Mirror coil 00003 to coil 00008
    mb->tab_bits[3] = coil_04; // Mirror coil 00004 to coil 00009
    mb->tab_bits[4] = coil_05; // Mirror coil 00005 tocoil 00010
    pthread_mutex_unlock(&g_lock);
}

// ===================== MAIN =====================

int main()
{
    modbus_t *ctx;
    modbus_mapping_t *mb_mapping;

    int server_socket;
    fd_set refset, rdset;
    int fdmax;

    uint8_t query[MODBUS_TCP_MAX_ADU_LENGTH];

    // Create Modbus context
    ctx = modbus_new_tcp("0.0.0.0", MODBUS_PORT);
    if (!ctx) {
        perror("modbus_new_tcp");
        return -1;
    }

    // Allocate registers
    mb_mapping = modbus_mapping_new( NB_COILS, 0, NB_REGISTERS, 0);
    if (!mb_mapping) {
        perror("modbus_mapping_new");
        return -1;
    }

    // Start Modbus server
    server_socket = modbus_tcp_listen(ctx, 10);

    FD_ZERO(&refset);
    FD_SET(server_socket, &refset);
    fdmax = server_socket;

    printf("Modbus TCP Server running on port %d...\n", MODBUS_PORT);

    // Start hardware thread
    pthread_t hw_thread;
    pthread_create(&hw_thread, NULL, hardware_thread, NULL);

    // Start IPC server (blocking until PyQt connects)
    ipc_init();

    while (1) {
        rdset = refset;

        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = 200000; // 200ms

        int rc_select = select(fdmax + 1, &rdset, NULL, NULL, &tv);

        if (rc_select == -1) {
            perror("select");
            break;
        }

        // Handle Modbus sockets
        for (int fd = 0; fd <= fdmax; fd++) {

            if (!FD_ISSET(fd, &rdset))
                continue;

            if (fd == server_socket) {
                int newfd = accept(server_socket, NULL, NULL);
                if (newfd != -1) {
                    FD_SET(newfd, &refset);
                    if (newfd > fdmax)
                        fdmax = newfd;

                    printf("New Modbus client: %d\n", newfd);
                }
            }
            else {
                modbus_set_socket(ctx, fd);

                int rc = modbus_receive(ctx, query);

                if (rc > 0) {
                    update_modbus_from_system(mb_mapping);
                    modbus_reply(ctx, query, rc, mb_mapping);
                    update_system_from_modbus(mb_mapping);
                    update_coils_from_system(mb_mapping); 
                }
                else {
                    printf("Client disconnected: %d\n", fd);
                    close(fd);
                    FD_CLR(fd, &refset);
                }
            }
        }

        // Handle IPC
        ipc_process();
    }

    close(server_socket);
    modbus_mapping_free(mb_mapping);
    modbus_free(ctx);

    return 0;
}