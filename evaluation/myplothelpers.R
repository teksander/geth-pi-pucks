library(ggplot2)
library(ggthemes)
library(directlabels)
library(grid)


data_summary <- function(data, varname, groupnames){
    require(plyr)
    summary_func <- function(x, col){
        c(mean = mean(x[[col]], na.rm=TRUE),
          sd = sd(x[[col]], na.rm=TRUE))
    }
    data_sum<-ddply(data, groupnames, .fun=summary_func,
                    varname)
    data_sum <- rename(data_sum, c("mean" = varname))
    
    return(data_sum)
}

base_breaks_x <- function(x){
  b <- x
  d <- data.frame(y=-Inf, yend=-Inf, x=min(b), xend=max(b))
  list(geom_segment(data=d, size=1.3, colour="gray35", aes(x=x, y=y, xend=xend, yend=yend), inherit.aes=FALSE),
#       geom_segment(data=d, size=1, colour="white", aes(x=xend, y = y, xend = xend+0.2, yend=yend), inherit.aes=FALSE),
       scale_x_continuous(breaks=b))
}

base_breaks_x_discrete<- function(x){
  b <- x
  d <- data.frame(y=-Inf, yend=-Inf, x=min(b), xend=max(b))
  list(geom_segment(data=d, size=1.3, colour="gray35", aes(x=x, y=y, xend=xend, yend=yend), inherit.aes=FALSE),
#       geom_segment(data=d, size=1, colour="white", aes(x=xend, y = y, xend = xend+0.2, yend=yend), inherit.aes=FALSE),
       scale_x_discrete(limits=b))
}

base_breaks_y <- function(x){
  b <- x
  d <- data.frame(x=-Inf, xend=-Inf, y=min(b), yend=max(b))
  list(geom_segment(data=d, size=1.3, colour="gray35", aes(x=x, y=y, xend=xend, yend=yend), inherit.aes=FALSE),
       scale_y_continuous(breaks=b))
}


#' Create a box-plot
plot.x.by.y <- function(df, x, y, xlab, ylab, out.name, report.dir, plot.expected.error=FALSE, start.x.at=0, extreme.outlier.count=NA, count.outliers=F, custom.base.breaks.x=c(0, 1, 2, 3, 4), custom.base.breaks.y=seq(0, 25, 5)) {

##    df <- df[df$byz >= start.x.at, ]
    
    p <- ggplot(df, aes_string(x=x, y=y)) +
        geom_boxplot(width=0.8, aes_string(group = x)) +
##        geom_smooth(method="loess", se=F) +
        ##        {if(plot.expected.error) geom_segment(x=0, xend=7, y=0, yend=7*3.75, lty=2)}+
        {if(plot.expected.error) geom_line(aes_string(x="byz", y="error.extrapolation"))}+
        {if(count.outliers) geom_text(data = extreme.outlier.count, aes(x=byz, y=72, label = paste0(percent.extreme.outliers, "%")))}+    
#        geom_segment(x=0, xend=7, y=0, yend=0, lty=2)+
#        coord_cartesian(clip = 'off') +
        theme_classic() +
        {if(plot.expected.error) geom_dl(aes(y=error.extrapolation, label = "expected error"), 
          method = list(dl.trans(x = x - 1.25, y = y + 0.2), "last.bumpup", cex = 1.0))}+
         theme(axis.text=element_text(size=15, colour="gray25"),
              axis.title=element_text(size=20, colour="gray25"),
              axis.line = element_blank(),              
              axis.ticks.length=unit(-0.25, "cm"),
              axis.ticks = element_line(colour = 'gray25'),
              panel.spacing.x=unit(.8, "lines"),
              legend.position="none",
              strip.background = element_rect(size = 1.3),
              axis.text.x = element_text(margin=unit(c(0.3,0.3,0.3,0.3), "cm"),
                                         angle = 0, vjust = 0, hjust=0.5),
              axis.text.y = element_text(margin=unit(c(0.5,0.5,0.5,0.5), "cm")))  +
        ylab(ylab) +
        xlab(xlab) +
        base_breaks_y(custom.base.breaks.y) +
    base_breaks_x(custom.base.breaks.x)

    out.name <- file.path(report.dir, out.name)
    print(out.name)
    ggsave(out.name, width=7, height=4)    
}



#' Create a box-plot
plot.bc.size <- function(df, x, y, xlab, ylab, out.name, report.dir,
                         start.x.at=0,
                         stop.x.at=Inf,
                         custom.base.breaks.x=c(0, 1, 2, 3, 4),
                         custom.base.breaks.y=seq(0, 25, 5)) {

#    df <- df[df$byz >= start.x.at, ]
    df <- df[df$TIME <= stop.x.at, ]
    df$num.robots <- as.factor(df$num.robots)
    df$liner <- df$num.robots + 1
    
    p <- ggplot(df, aes_string(x=x, y=y,
                               group="num.robots"
#                         shape="num.robots"
#                         fill="num.robots"
                               )) +
    scale_linetype_manual(values=c("dotdash", "dashed", "dotted", "longdash"))+
    geom_smooth(aes_string(linetype="num.robots"),
                method = lm,
                level=0.99,
                color="black") +
        theme_classic() +
#        geom_dl(aes(label=group),method="last.points") + 
         theme(axis.text=element_text(size=15, colour="gray25"),
               axis.title=element_text(size=20, colour="gray25"),
               axis.line = element_blank(),              
               axis.ticks.length=unit(-0.25, "cm"),
               axis.ticks = element_line(colour = 'gray25'),
               panel.spacing.x=unit(.8, "lines"),
              legend.position="none",
              strip.background = element_rect(size = 1.3),
              axis.text.x = element_text(margin=unit(c(0.3,0.3,0.3,0.3), "cm"),
                                         angle = 0, vjust = 0, hjust=0.5),
              axis.text.y = element_text(margin=unit(c(0.5,0.5,0.5,0.5), "cm")))  +
             ylab(ylab) +
        xlab(xlab) +
        base_breaks_y(custom.base.breaks.y) +
    base_breaks_x(custom.base.breaks.x)

#    direct.label(p, list('last.points', colour='black'))
    
    out.name <- file.path(report.dir, out.name)
    print(out.name)
    ggsave(out.name, width=7, height=4)    
}
