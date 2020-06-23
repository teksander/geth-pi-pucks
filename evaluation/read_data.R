#' Read data for ANTS 2020 paper and create plots for the Experiments
#' section of the paper

source("myplothelpers.R")
library(stringr)

#' TODO!: Currently, the mean is taken from the robot that received
#' the consensus signal at last; instead: randomly sample one robots.

# General Settings ------------------------------------------------------
actual.frequency <- 32 ## Actual frequency of white tiles
base.dir <- "../"
multiplier <- 10000000
tau <- 0.02
data.dir <- file.path(base.dir, "results")
plot.dir <- file.path(base.dir, "evaluation", "plots")

# Function Declarations -------------------------------------------------

#' Get the mean where a consensus has been reached from an event.csv
#' file
get_final_mean <- function(event.df, consensus.reached.at) {
    means <- event.df$MEAN
    final.mean <- means[consensus.reached.at] / 100000

    return(final.mean)
}

#' TODO: One function for both values
get_final_time <- function(event.df, consensus.reached.at) {
    times <- event.df$TIME
    final.time <- times[consensus.reached.at]

    return(final.time)
}

find.consensus <- function(sc.df, num.robots, tau) {

    # Find position in dataframe where the consensus is reached for
    # the first time
    pos <- min(which(sc.df$C == "True"))

    # Return position and time of positions
    return(c(pos, sc.df$TIME[pos]))
}

postprocess <- function(run.path, tau) {

    # Find number of robots again (TODO: use as argument)
    num.robots <- strtoi(str_match(run.path,
                            "(\\d+)rob-(\\d)byz-(\\d+)$")[2])


    robots <- list.dirs(run.path, recursive = FALSE)
    all.event.logs <- file.path(robots, "sc.csv")

    all.consensus.reached.at.time <- c()
    all.consensus.reached.at.pos <- c()

    print(all.event.logs)
    for (event.file in all.event.logs) {
        event.df <- read.csv(event.file, sep=' ')

        # Get consensus time and position in dataframe
        cons.time.and.position <-  find.consensus(event.df,
                                                  num.robots,
                                                  tau)

        consensus.reached.at.pos <- cons.time.and.position[1]
        consensus.reached.at.time <- cons.time.and.position[2]


        
        all.consensus.reached.at.time <- c(all.consensus.reached.at.time,
                                           consensus.reached.at.time)

        all.consensus.reached.at.pos <- c(all.consensus.reached.at.pos,
                                          consensus.reached.at.pos)
        
    }

    error.file <- "none"
    
    # Which event.df contained the maximum time?
    max.time.pos <- which.max(all.consensus.reached.at.time)
    print(all.consensus.reached.at.time)
    print(max.time.pos)

    if (length(max.time.pos) == 0) {
        consensus.reached.at <- NA
        final.mean <- NA
        final.time <- NA
        error.file <- "all.failed"

    ##  Check if all robots received a consensus signal

     } else if (any(is.na(all.consensus.reached.at.time))) {
         consensus.reached.at <- NA
         final.mean <- NA
         final.time <- NA
         error.file <- all.event.logs[min(which(is.na(all.consensus.reached.at.time)))]

    } else {
        # At which position is the consenus agreement in that df?
        consensus.reached.at <-  all.consensus.reached.at.pos[max.time.pos]

        event.df <- read.csv(all.event.logs[max.time.pos], sep=' ')


        # We take the mean of the robot that reached consensus last;
        # it's better to sample a random robot
        final.mean <- get_final_mean(event.df, consensus.reached.at)

        final.time <- get_final_time(event.df, consensus.reached.at)

    }

    return(c(consensus.reached.at,
             final.mean,
             final.time,
             error.file))
    }


#' Create a dataframe of all runs and calculate the absolute error
create.df <- function(experiment.path, tau) {
    experiments <- list.dirs(experiment.path, recursive=FALSE,
                             full.names = FALSE)
    print(experiments)
    experiments.with.path <- list.dirs(experiment.path,
                                       recursive=FALSE)
    
    # Extract information about that run using a regex:
    # - Number of robots
    # - Number of Byzantines 
    ##### WARNING (TODO): Compare byzantines in filename to robots with estimate == 0
    # - Repetition number
    all.experiments.matrix <- str_match(experiments,
                                        "^(\\d+)rob-(\\d)byz-(\\d+)$")

    # Create a data frame with all information from all runs
    df <- as.data.frame(all.experiments.matrix)
    colnames(df) <- c("path", "num.robots", "byz", "run")
    df$num.robots <- as.numeric(as.character(df$num.robots))
    df$byz <- as.numeric(as.character(df$byz))

    df$full.path <- experiments.with.path
    df <- na.omit(df) # Remove invalid runs

    # Needed are:
    # - position of consensus
    # - the final mean
    # - consensus time


    print(df)

    postprocessed <- lapply(df$full.path, postprocess, tau)
    postprocessed.df <- data.frame(matrix(unlist(postprocessed),
                                          nrow=length(postprocessed),
                                          byrow=T))

    colnames(postprocessed.df) <- c("consensus.reached.at",
                                    "final.mean",
                                    "final.time",
                                    "error.file")

    df <- cbind(df, postprocessed.df)

    df$consensus.reached.at <- as.numeric(as.character(df$consensus.reached.at))
    df$final.mean <- as.numeric(as.character(df$final.mean))
    df$final.time <- as.numeric(as.character(df$final.time))
    df$error.file <- as.character(df$error.file)
    
    df$selected.absError <- abs(df$final.mean - actual.frequency)

    return(df)
}

#' Iterate over all files and extract the blockchain size based on the
#' time of the experiment
create.bcsize.by.time <- function(df.runs) {

df <- data.frame(TIME=numeric(),
                 CHAINDATASIZE=numeric(), 
                 stringsAsFactors=FALSE) 

    i <- 1
    for (run.path in df.runs$full.path) {
        robots <- list.dirs(run.path, recursive = FALSE)
        all.event.logs <- file.path(robots, "extra.csv")

        for (event.file in all.event.logs) {    
            event.df <- read.csv(event.file, sep=' ')
            event.df <- event.df[,c("TIME", "CHAINDATASIZE")]      
            event.df$CHAINDATASIZE <- event.df$CHAINDATASIZE / 1000000      
            event.df$num.robots <- df.runs$num.robots[i]
            
            df <- rbind(df, event.df)    
        }
        i <- i + 1        
    }
    df$CHAINDATASIZE <- as.numeric(as.character(df$CHAINDATASIZE))
    
    return(df)
}


# Experiment 1  ------------------------------------------------------------

experiment.1.path <- file.path(data.dir, "experiment_1")
df.1 <- create.df(experiment.1.path, tau)

# Plot selected absolute error
plot.x.by.y(df.1,
            x="byz",
            y="selected.absError",
            xlab=expression("Number of Byzantine robots"),
            ylab=expression("Absolute error (in %)"),
            out.name=sprintf("exp1_error.pdf"),
            report.dir=plot.dir,
            custom.base.breaks.x=c(0,1,2,3,4))

# Plot consensus time
plot.x.by.y(df.1,
            x="byz",
            y="final.time",
            xlab=expression("Number of Byzantine robots"),
            ylab=expression("Consensus time (s)"),
            out.name=sprintf("exp1_time.pdf"),
            report.dir=plot.dir,
            custom.base.breaks.x=c(0,1,2,3,4),
            custom.base.breaks.y=c(0,1000,2000))




# Neighbors analysis per X seconds ---------------------------------------------

create.neighbors.by.num.robots <- function(df.runs, X=15) {

    df <- data.frame(neighbors.per.Xsec=numeric(),
                     num.robots=numeric(),
                     avg.block.time=numeric(),
                     stringsAsFactors=FALSE) 

    i <- 1
    for (run.path in df.runs$full.path) {
        robots <- list.dirs(run.path, recursive = FALSE)
        all.buffer.logs <- file.path(robots, "buffer.csv")

        for (buffer.file in all.buffer.logs) {
            print(buffer.file)

            buffer.df <- read.csv(buffer.file,
                                  sep=' ',
                                  header=F,
                                  skip=1,
                                  col.names = paste0("V",seq_len(14)),
                                  fill = TRUE)

            buffer.df <- buffer.df[,c("V2", "V3", "V4", "V5")]
            colnames(buffer.df) <- c("TIME", "BLOCK", "BUFFER", "GETH")

            
            # WARNING: Replace this plot with average of the column TELAPSED in block.log. x axis: number of robots; y axis: block travel time


            logging.frequency <- 1/2  # 1 log per 2 seconds
            sum.neighbors <- sum(buffer.df$GETH)
            neighbors.per.Xsec <- (X * (sum.neighbors / max(buffer.df$TIME))) / logging.frequency
            
            buffer.df$num.robots <- df.runs$num.robots[i]
            buffer.df$neighbors.per.Xsec <- neighbors.per.Xsec
            blocks <- buffer.df$BLOCK
            # WARNING: THIS CAN BE IMPROVED; todo: instead of reading from buffer.log read from block.log last entry
            avg.block.time <- max(buffer.df$TIME) / (blocks[length(blocks)] - blocks[1])

            small.df <- data.frame(neighbors.per.Xsec=neighbors.per.Xsec,
                                   num.robots=df.runs$num.robots[i],
                                   avg.block.time=avg.block.time)

            print(small.df)
            
            df <- rbind(df, small.df)    
        }
        i <- i + 1        
    }
    
    return(df)
}


neighbors.df <- create.neighbors.by.num.robots(df.1)

## Plots neighbor per X (e.g., 15) seconds
plot.x.by.y(neighbors.df,
            x="num.robots",
            y="neighbors.per.Xsec",
            xlab="Number of robots",
            ylab="Encounters(15).",
            out.name="encounters_plot.pdf",
            report.dir=plot.dir,
            custom.base.breaks.x=c(5, 7, 8, 10),
            custom.base.breaks.y=c(0.00, 0.5, 1.0, 1.5, 2.0, 2.5))


# Block time analysis -----------------------------------------------------

## Plots average block time
plot.x.by.y(neighbors.df,
            x="num.robots",
            y="avg.block.time",
            xlab="Number of robots",
            ylab="Average block time",
            out.name="blocktime.pdf",
            report.dir=plot.dir,
            custom.base.breaks.x=c(5,7,8,10),
            custom.base.breaks.y=c(0.00, 20, 40, 60, 80))



# Blockchain growth analysis -----------------------------------------------------


df.robots <- create.bcsize.by.time(df.1)

plot.bc.size(df.robots,
             "TIME",
             "CHAINDATASIZE",
             "Time in seconds",
             "Blockchain size in MB",
             "blockchain_growth.pdf",
             plot.dir,
             stop.x.at=900,
             custom.base.breaks.x=c(0, 300, 600, 900),
             custom.base.breaks.y=c(0, 0.1, 0.2, 0.3, 0.4)
             )
