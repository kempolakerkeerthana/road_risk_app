class Board{
    String message=null;
    public synchronized void read()
    {
        while(message==null){
            try{
                wait();
            }catch(InterruptedException e){
                e.printStackTrace();
            }
        }
        System.out.println(Thread.currentThread().getName()
    
    
    )
    }
    
    public synchronized void write()
    {
        while(message!=null){
            try{
                wait();
            }catch(InterruptedException e){
                e.printStackTrace();
            }
        }
    }
    class Board implements Runnable{
        
    
}