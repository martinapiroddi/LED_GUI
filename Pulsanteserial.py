import sys

import time

import logging

from PyQt5 import QtCore
from PyQt5.QtCore import (
    QObject,
    QThreadPool, 
    QRunnable, 
    pyqtSignal, 
    pyqtSlot
) #tutti strumenti per gestire il multithredding 

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QWidget,
)
#tutti strumenti che servono per gestire il multithreading
import serial #per gestire la comunicazione seriale
import serial.tools.list_ports

#Questo programma fa una scansione delle porte attive sul pc
# Globals
CONN_STATUS = False #variabile globale che tiene traccia dello stato della connessione


# Logging config
logging.basicConfig(format="%(message)s", level=logging.INFO) #configurazione equivalente al print 
#con level andiamo a settare il grado di importanza dei messaggi oltre al quale vengono visualizzati, INFO è uno dei più bassi. Scritto così fa in modo che vengano visualizzati a schermo solo i messaggi
# a livello info o superiori, inferiori al livello INFO non vengono visualizzati
#########################
# SERIAL_WORKER_SIGNALS #
#########################
class SerialWorkerSignals(QObject): #Si definisisce una classe figlia, il nome è come quello del thread parallelo SerialWorker
    """!
    @brief Class that defines the signals available to a serialworker.

    Available signals (with respective inputs) are:
        - device_port:
            str --> port name to which a device is connected
        - status:
            str --> port name
            int --> macro representing the state (0 - error during opening, 1 - success)
    """
    device_port = pyqtSignal(str) #andiamo a definire due segnali
    status = pyqtSignal(str, int) #è un intero che mi serve per capire se l'apertura della porta è andata a buon fine o no
#device port emetterà come segnale una stringa--> lo utilizzerò facendogli portare il nome della porta alla quale sono connesso
#status ha due tipi di dato perchè èprta sia l'informazione sul nome della porta ma anche un intero ==> 0  se l'apertura della porta non è
#andata buon fine, 1 se è andato tutto bene
#################
# SERIAL_WORKER #
#################
class SerialWorker(QRunnable):
    """!
    @brief Main class for serial communication: handles connection with device.
    """
    def __init__(self, serial_port_name):
        """!
        @brief Init worker.
        """
        self.is_killed = False #è una variabile booleana che potrebbe essere usata per un controllo per chiudere la porta--> il QRunnable si ferma
        super().__init__()
        # init port, params and signals
        self.port = serial.Serial() #variabile 
        self.port_name = serial_port_name
        self.baudrate = 9600 # hard coded but can be a global variable, or an input param
        self.signals = SerialWorkerSignals() #all'interno dell'init creo un'istanza dei miei segnali. Ora i segnali saranno disponibili
        #all'interno di self.signals

    @pyqtSlot() #decoratore
    def run(self): #il run è l'unico metodo che va obbligatoriamente chiamato così perchè quando viene inizializzato un thread parallelo 
        #all'interno della main window viene lanciato il metodo run. Tutto quello che vogliamo che venga
        # fatto dal thread parallelo deve stare qua dentro. Non esce da qua finchè non ha finito di fare tutto e poi dopo
        #il thread parallelo è morta; a meno che non si usi lo strumento thread pool che permette di riavviarlo
        """!
        @brief Estabilish connection with desired serial port.
        """
        global CONN_STATUS

        if not CONN_STATUS: #se niente è connesso
            try: #prova ad aprire l aporta, se non ci riesce internamente genera un errore (SerialException)
                self.port = serial.Serial(port=self.port_name, baudrate=self.baudrate,
                                        write_timeout=0, timeout=2) #importante essersi salvati tutti i parametri della porta perchè possono essercene diverse               
                if self.port.is_open: #se la porta è aperta lo status diventa True, allora mando un segnale
                    CONN_STATUS = True
                    self.signals.status.emit(self.port_name, 1) #sto mandando un segnale, invio un segnale con .emit e invio il nome della porta (il thread principale 
                    #deve sapere quale porta) e l'intero 1 che indica che la connessione è avvenuta
                    time.sleep(0.01)     #bloccando il codice per 0.01 sec, è necessario perchè spesso serve un attimo a far allineare i dispositivi
            except serial.SerialException: #se non riesce ad aprire la porta viene generato l'errore SerialException
                logging.info("Error with port {}.".format(self.port_name)) #allora il print (usando il logging), passando come parametro la porta che stavamo analizzando
                self.signals.status.emit(self.port_name, 0) #e poi mando sempre il segnale però con 0
                time.sleep(0.01)
    #fino ad ora abbiamo solo gestito segnali e thread parallelo, bisogna ancora definire un'interfaccia --> main window 
    @pyqtSlot()
    def send(self, char): #il metodo send serve a mandare un carattere su una porta seriale, serve per creare la connessione 
        #SERVE PER IL COMPITO
        """!
        @brief Basic function to send a single char on serial port.
        """
        try:
            self.port.write(char.encode('utf-8'))
            logging.info("Written {} on port {}.".format(char, self.port_name))
        except:
            logging.info("Could not write {} on port {}.".format(char, self.port_name))

   
    @pyqtSlot()
    def killed(self):
        """!
        @brief Close the serial port before closing the app.
        """
        global CONN_STATUS
        if self.is_killed and CONN_STATUS:
            self.port.close()
            time.sleep(0.01)
            CONN_STATUS = False
            self.signals.device_port.emit(self.port_name)

        logging.info("Killing the process")


###############
# MAIN WINDOW #
###############
class MainWindow(QMainWindow):
    def __init__(self):
        """!
        @brief Init MainWindow.
        """
        # define worker
        self.serial_worker = SerialWorker(None) #stiamo inizializzando vuoto il nostro thread paralleo, non so ancora qual è il nome della porta

        super(MainWindow, self).__init__()

        # title and geometry
        self.setWindowTitle("COMANDO LED SU SERIALE")
        width = 400
        height = 320
        self.setMinimumSize(width, height)

        # create thread handler
        self.threadpool = QThreadPool() #IMPORTANTE: Inizializzazione del threadpool che è quel contenitore che gestisce i thread

        self.connected = CONN_STATUS
        self.serialscan() #fa uno scan delle porte seriali per vedere quali son attive. va chiamata prima di initUI, è una funzione creata da me 
        self.initUI()


    #####################
    # GRAPHIC INTERFACE #
    #####################
    def initUI(self):
        """!
        @brief Set up the graphical interface structure.
        """
        # layout, solito menu a tendina e pulsante
        button_hlay = QHBoxLayout()
        button_hlay.addWidget(self.com_list_widget)
        button_hlay.addWidget(self.conn_btn)
        
        
        # pulsante per spedire un char
        button_hlay.addWidget(self.send_btn)
        
        widget = QWidget()
        widget.setLayout(button_hlay)
        self.setCentralWidget(widget)


    ####################
    # SERIAL INTERFACE #
    ####################
    def serialscan(self):
        """!
        @brief Scans all serial ports and create a list.
        """
        # create the combo box to host port list
        self.port_text = ""
        self.com_list_widget = QComboBox()
        self.com_list_widget.currentTextChanged.connect(self.port_changed)  #ho connesso un sengale del menu a tendina
        #significa che ogni qual volta cambia il testo visualizzato nel menu a tendina cambia. Stiamo associando l'evento ad un segnale
        
        # create the connection button
        
        self.conn_btn = QPushButton(
            text=("Connect to port {}".format(self.port_text)), 
            checkable=True,
            toggled=self.on_toggle #il segnale generato è toggled, ogni qual volta cambia stato
            #il pulsante ora ha anche uno stato, nel senso che lo si può riportare allo stato non premuto
        )

        # create the send button

        self.send_btn = QPushButton(
            text=("DISABILITATO"), 
            checkable=True,
            toggled=self.on_send #il segnale generato è toggled, ogni qual volta cambia stato
            #il pulsante ora ha anche uno stato, nel senso che lo si può riportare allo stato non premuto
        )       
        self.send_btn.setDisabled(True) 

        #ora vogliamo effettivamente fare uno scan delle porte seriali, quello che facciamo è creare una lista
        # acquire list of serial ports and add it to the combo box
        serial_ports = [
                p.name #prendiamo il nome 
                for p in serial.tools.list_ports.comports() #maniera compatta per creare un ciclo for all'interno della lista che sto creando, 
                #la funzione è già oresente nella librearia serial, prendi i nomi che trova delle porte facendo lo scan
            ]
        self.com_list_widget.addItems(serial_ports)

    #ora che abbiamo definito i segnali dobbiamo creare le funzioni che permettano di collegarli tra di loro, il metodo chiave è ontoggle
    ##################
    # SERIAL SIGNALS #
    ##################
    def port_changed(self):
        """!
        @brief Update conn_btn label based on selected port.
        """
        self.port_text = self.com_list_widget.currentText()
        self.conn_btn.setText("Connect to port {}".format(self.port_text))
#on toggle rispetto al clicked ha anche uno dato associato allo stato del pulsante. Il pulsante in questo caso è di tipologia checkable. dipendentemente dello 
#stato del pulsante devo fare due cose diverse. Quindi serve una variabile booleana che è checked-->il segnale porta quell'informazione
    @pyqtSlot(bool)
    def on_toggle(self, checked): 
        """!
        @brief Allow connection and disconnection from selected serial port.
        """
        if checked: #se il pulsante è stato premuto mi devo connettere alla porta, ma questo lo voglio fare nel thread parallelo, non nel main thread.
            # setup reading worker. Quindi set up del thread parallelo e gli do il nome della porta che deve aprire ( quella che era stata messa nel menu a tendina)
            self.serial_worker = SerialWorker(self.port_text) # needs to be re defined
            # connect worker signals to functions. Connetto i due segnali a due slot che utilizzerò per analizzare questi segnali
            self.serial_worker.signals.status.connect(self.check_serialport_status)
            self.serial_worker.signals.device_port.connect(self.connected_device)
            #così ho solo creato il thread parallelo, ora lo devo lanciare con lo start
            # execute the worker
            self.threadpool.start(self.serial_worker) #lancia automaticamente il metodo run, quindi quando premete il pulsante il thread parallelo viene lanciato e il metodo
            #run apre la porta seriale. Però non abbiamo ancora cambiato niente sulla scritta del pulsante, per fare questo sfrutto il segnale di status
            #Il valore di status dipende da se è riuscito o meno a connettersi
            self.send_btn.setDisabled(False) 
            self.send_btn.setText("ACCENDI")            


        else: #il toggle non sarà più checked
            # kill thread    termina il thread perchè l'utente vuole terminare la comunicazione su quella porta 
            self.serial_worker.is_killed = True
            self.serial_worker.killed()
            self.com_list_widget.setDisabled(False) # enable the possibility to change port, riabilito il menu a tendina che avevp disabilitato prima quando era connesso
            self.conn_btn.setText("Connect to port {}".format(self.port_text))
            self.send_btn.setDisabled(True) 
            self.send_btn.setText("DISABILITATO")

            
    

    @pyqtSlot(bool)
    def on_send(self, checked): 
        """!
        @brief Allow send a 0 char to turn OFF the LED or a 1 char to TURN ON the LED.
        """
        if checked: #se il pulsante è stato premuto devo inviare uno "0" e cambiare il testo del pulsante.
            self.serial_worker.send("0")
            self.send_btn.setText("SPENGNI");            
        else: #il toggle non sarà più checked
            #se il pulsante è stato premuto devo inviare uno "1" e cambiare il testo del pulsante.
            self.serial_worker.send("1")
            self.send_btn.setText("ACCENDI");
    

    def check_serialport_status(self, port_name, status): #va a vedere se è riuscito o no a connettersi
        """!
        @brief Handle the status of the serial port connection.

        Available status:
            - 0  --> Error during opening of serial port
            - 1  --> Serial port opened correctly
        """
        if status == 0:
            self.conn_btn.setChecked(False) #se la connessione non è riuscita devo far tornare il pulsante nello stato di non premuto
            self.send_btn.setDisabled(True) 
            self.send_btn.setText("DISABILITATO")
            self.send_btn.checkable=False
        elif status == 1: #il pulsante è riuscito a connettersi al psoc, e solo a quel punto cambio lo stato del pulsante e il testo 
            # enable all the widgets on the interface
            self.com_list_widget.setDisabled(True) # disable the possibility to change COM port when already connected, importante disabilitare il widget del menu a tendina 
            #altrimenti si rischia che l'utente selezioni un'altra comma, il concetto è che bisogna supporre l'utente peggiore possibile. Bisogna prevedere i possibili utilizzi sbagliati
            self.send_btn.setDisabled(False) 
            self.send_btn.setText("ACCENDI")
            #self.send_btn.checkable=True
            #self.send_btn.setEnabled
            
            self.conn_btn.setText(
                "Disconnect from port {}".format(port_name)
            )

    def connected_device(self, port_name):
        """!
        @brief Checks on the termination of the serial worker.
        """
        logging.info("Port {} closed.".format(port_name))


    def ExitHandler(self):
        """!
        @brief Kill every possible running thread upon exiting application.
        """
        self.serial_worker.is_killed = True
        self.serial_worker.killed()




#############
#  RUN APP  #
#############
if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    app.aboutToQuit.connect(w.ExitHandler)
    w.show()
    sys.exit(app.exec_())